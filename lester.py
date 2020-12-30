import asyncio
import configparser
import logging
import os
import pickle
import re
from datetime import datetime

import apraw
import discord
from apraw.utils import BoundedSet
from banhammer import Banhammer
from banhammer.models import EventHandler, ItemAttribute, RedditItem, Subreddit
from discord.ext import commands
from discord.ext.commands import Bot
from discord.utils import escape_markdown

import firebase
import stats
from cmds import HelpCommand
from config import config as lc_config
from helpers import MessageBuilder

logger = logging.getLogger("banhammer")

formatter = logging.Formatter(u'%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fileHandle = logging.FileHandler('banhammer.log')
fileHandle.setFormatter(formatter)
fileHandle.setLevel(logging.WARNING)
logger.addHandler(fileHandle)

reddit = apraw.Reddit("LCB")
gta_green = discord.Colour(0).from_rgb(207, 226, 206)

intents = discord.Intents.default()
intents.members = True


class LesterCrest(Bot, Banhammer):
    def __init__(self, **options):
        super().__init__(lc_config["command_prefix"], help_command=HelpCommand(gta_green),
                         description="/r/gtaonline's moderation bot using Banhammer.py.", intents=intents,
                         **options)
        Banhammer.__init__(self, reddit, bot=self, embed_color=gta_green, message_builder=MessageBuilder(),
                           change_presence=lc_config["change_presence"])

        self._new_ids = BoundedSet(301)
        self._comment_ids = BoundedSet(301)
        self._report_ids = BoundedSet(301)

        with open("assets/DirtyWords_en.txt") as f:
            self.words = f.read().splitlines()
            self.word_patterns = [re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE) for w in self.words]

        self.action_stats = {
            t: stats.get_users_action_count(stats.split_actions_by_user(payloads)) for t,
            payloads in stats.get_actions_by_type().items()}
        self.stats_updated = True

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, discord.ext.commands.errors.CommandNotFound):
            pass
        else:
            print(f"Error in command: {error}")

    async def on_handler_error(self, error):
        print(f"Error in handler: {error}")

    async def on_ready(self):
        print(f"{self.user} is running.")

        for sub in lc_config["subreddits"]:
            s = Subreddit(self, **sub)
            await s.load_reactions()
            await self.add_subreddits(s)

        channel = self.get_channel(734713971428425729)
        message = await channel.fetch_message(736613065889546321)

        for sub in self.subreddits:
            embed = await sub.get_reactions_embed(embed_template=self.embed)
            try:
                await message.edit(embed=embed)
            except Exception as e:
                print(f"Error setting subreddit reactions embed: {e}")
            break

        Banhammer.start(self)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        item = await self.get_item(message.content)
        if item:
            await item.add_reactions(message)

        await self.process_commands(message)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        c = self.get_channel(payload.channel_id)

        if not isinstance(c, discord.TextChannel):
            return

        u = c.guild.get_member(int(payload.user_id))
        if u.bot:
            return
        if not any(role.id == 734714209342062602 for role in u.roles):
            return

        try:
            m = await c.fetch_message(payload.message_id)
        except Exception as e:
            print(f"Error fetching message: {e}")
            return

        e = payload.emoji.is_custom_emoji() and f"<:{payload.emoji.name}:{payload.emoji.id}>" or payload.emoji.name

        item = await self.get_item(m.embeds[0] if m.embeds else m.content)
        if not item:
            return

        reaction = item.get_reaction(e)

        if not reaction:
            return

        msg = None
        approved_by = getattr(item.item, "approved_by", "")
        removed_by = getattr(item.item, "removed_by", "")
        action_author = escape_markdown(approved_by or removed_by) if any((approved_by, removed_by)) else ""

        if action_author and action_author.lower() != "automoderator":
            author_name = escape_markdown(str(await item.get_author_name()))
            action_taken = "approved" if approved_by else "removed" if removed_by else ""
            reaction_action = "reply to" if reaction.reply else "approve" if reaction.approve else "remove"

            if reaction.reply or (reaction.approve and removed_by) or (not reaction.approve and approved_by):
                msg = f"The {item.type} by /u/{author_name} was already {action_taken} by /u/{action_author}, are you sure you want to {reaction_action} it?\n\n" \
                    f"{item.url}"

        if msg:
            msg = await u.send(msg)
            await msg.add_reaction("✔")
            await msg.add_reaction("❌")

            try:
                r = await self.wait_for("reaction_add",
                                        check=lambda _r, _u: _u.id == u.id and _r.message.id == msg.id,
                                        timeout=2 * 60)
                await msg.delete()

                if r[0].emoji != "✔":
                    return
            except asyncio.exceptions.TimeoutError:
                await u.send("❌ That took too long! You can restart the process by reacting to the item again.")
                return

        result = await reaction.handle(item, user=u.nick)

        try:
            await m.delete()
        except Exception as e:
            print(f"Failed to delete message: {e}")
            return

        if result.approved:
            channel = self.get_channel(lc_config["approved_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))
        elif any("banned" in action for action in result.actions):
            channel = self.get_channel(lc_config["banned_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))
        else:
            channel = self.get_channel(lc_config["removed_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))

            if not await item.is_author_removed():
                for reaction in item.reactions:
                    if reaction.ban is not None:
                        await message.add_reaction(reaction.emoji)

        if item.type in ["submission", "comment"]:
            self.stats_updated = True
            self.action_stats[f"{item.type}s"][result.user] = self.action_stats[f"{item.type}s"].get(
                result.user, 0) + 1

        d = await result.to_dict()
        with open(lc_config["payloads_file"], "ab+") as f:
            pickle.dump(d, f)
        firebase.db.collection("mod_actions").add(d)

    @property
    def embed(self):
        embed = discord.Embed(colour=gta_green)
        embed.set_footer(text="Lester Crest Bot", icon_url=self.user.avatar_url)
        embed.timestamp = datetime.utcnow()
        return embed

    @EventHandler.new()
    async def handle_new(self, item: RedditItem):
        self._new_ids.add(item.item.id)
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["new_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.comments()
    @EventHandler.filter(ItemAttribute.AUTHOR, "automoderator", "lestercrestbot", "repostsleuthbot", reverse=True)
    async def handle_comments(self, item: RedditItem):
        self._comment_ids.add(item.item.id)
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["comments_channel"]).send(embed=embed)
        await item.add_reactions(msg)

        if any(pattern.search(item.body.lower()) for pattern in self.word_patterns):
            msg = await self.get_channel(lc_config["no_no_words_channel"]).send(embed=embed)
            await item.add_reactions(msg)

    @EventHandler.comments()
    @EventHandler.filter(ItemAttribute.AUTHOR, "repostsleuthbot")
    async def handle_reposts(self, item: RedditItem):
        self._comment_ids.add(item.item.id)
        try:
            submission = await item.item.submission()
        except Exception as e:
            print(f"Couldn't fetch comment's parent submission: {e}")
        else:
            submission_item = RedditItem(submission, item.subreddit, "reports")
            embed = await submission_item.get_embed(embed_template=self.embed)

            embed.add_field(name="Comment by /u/RepostSleuthBot",
                            value=f"{item.body}\n\n[Comment.]({item.url})")

            msg = await self.get_channel(lc_config["reposts_channel"]).send(embed=embed)
            await submission_item.add_reactions(msg)

    @EventHandler.mail()
    async def handle_mail(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["mail_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.reports()
    async def handle_reports(self, item: RedditItem):
        self._report_ids.add(item.item.id)
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["reports_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.queue()
    async def handle_queue(self, item: RedditItem):
        if any(item.item.id in ids for ids in (self._new_ids, self._comment_ids, self._report_ids)):
            return
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["queue_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.mod_actions()
    async def handle_actions(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["actions_channel"]).send(embed=embed)
        await item.add_reactions(msg)


extensions = ["cogs.mod_cog"]


if __name__ == "__main__":
    bot = LesterCrest()

    for extension in extensions:
        bot.load_extension(extension)
        print(f"{extension} loaded.")

    config = configparser.ConfigParser()
    config.read("discord.ini")

    bot.run(config["LCB"]["token"])
