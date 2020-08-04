import asyncio
import configparser
import logging
import os
import pickle
import re
from datetime import datetime

import apraw
import banhammer
import discord
from banhammer import Banhammer
from banhammer.models import EventHandler, ItemAttribute, RedditItem, Subreddit
from discord.ext import commands
from discord.ext.commands import Bot
from discord.utils import escape_markdown

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


class LesterCrest(Bot, Banhammer):
    def __init__(self, **options):
        super().__init__(lc_config["command_prefix"], help_command=HelpCommand(gta_green),
                         description="/r/gtaonline's moderation bot using Banhammer.py.", **options)
        Banhammer.__init__(self, reddit, bot=self, embed_color=gta_green, message_builder=MessageBuilder(),
                           change_presence=lc_config["change_presence"])

        with open("assets/DirtyWords_en.txt") as f:
            self.words = f.read().splitlines()
            self.word_patterns = [re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE) for w in self.words]

        self.user_stats = stats.get_actions_by_user()
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
            await message.edit(embed=embed)
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

        u = c.guild.get_member(payload.user_id)
        if u.bot:
            return
        if not any(role.id == 734714209342062602 for role in u.roles):
            return

        m = await c.fetch_message(payload.message_id)
        e = payload.emoji.is_custom_emoji() and f"<:{payload.emoji.name}:{payload.emoji.id}>" or payload.emoji.name

        item = await self.get_item(m.embeds[0] if m.embeds else m.content)
        if not item:
            return

        reaction = item.get_reaction(e)

        if not reaction:
            return

        try:
            await m.delete()
        except Exception as e:
            print(f"Failed to delete message: {e}")
            return

        msg = None
        author_name = escape_markdown(str(await item.get_author_name()))

        if reaction.reply:
            if approved_by := getattr(item.item, "approved_by", "") and approved_by.lower() != "automoderator":
                msg = f"The submission by /u/{author_name} was already approved by /u/{escape_markdown(approved_by)}, are you sure you want to remove it?\n\n" \
                    f"{item.url}"
            elif removed_by := getattr(item.item, "removed_by", "") and removed_by.lower() != "automoderator":
                msg = f"The submission by /u/{author_name} was already removed by /u/{escape_markdown(removed_by)}, are you sure you want to approve it?\n\n" \
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

        if result.approved:
            channel = self.get_channel(lc_config["approved_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))
        elif any("banned" in action for action in result.actions):
            channel = self.get_channel(lc_config["banned_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))
        else:
            channel = self.get_channel(lc_config["removed_channel"])
            message = await channel.send(embed=await result.get_embed(embed_template=self.embed))

            for reaction in item.get_reactions():
                if reaction.ban is not None:
                    await message.add_reaction(r.emoji)

        self.stats_updated = True
        self.user_stats[result.user] = self.user_stats.get(result.user, 0) + 1

        with open(lc_config["payloads_file"], "ab+") as f:
            pickle.dump(result.to_dict(), f)

    @property
    def embed(self):
        embed = discord.Embed(colour=gta_green)
        embed.set_footer(text="Lester Crest Bot", icon_url=self.user.avatar_url)
        embed.timestamp = datetime.now()
        return embed

    @EventHandler.new()
    async def handle_new(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["new_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.comments()
    @EventHandler.filter(ItemAttribute.AUTHOR, "automoderator", "lestercrestbot", "repostsleuthbot", reverse=True)
    async def handle_comments(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["comments_channel"]).send(embed=embed)
        await item.add_reactions(msg)

        if any(pattern.search(item.body.lower()) for pattern in self.word_patterns):
            msg = await self.get_channel(lc_config["no_no_words_channel"]).send(embed=embed)
            await item.add_reactions(msg)

    @EventHandler.comments()
    @EventHandler.filter(ItemAttribute.AUTHOR, "repostsleuthbot")
    async def handle_reposts(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)

        try:
            submission = await item.item.submission()
        except Exception as e:
            print(e)
        else:
            embed.add_field(name="Parent submission",
                            value=f"[Submission](https://reddit.com{submission.permalink}) by /u/{submission._data['author']}")

            if submission.is_self:
                embed.add_field(name="Body", value=item.body, inline=False)
            elif "i.redd.it" in submission.url or any(submission.url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif")):
                embed.set_image(url=submission.url)
            elif not submission._data.get("poll_data", None):
                embed.add_field(name="URL", value=escape_markdown(submission.url),
                                inline=False)
            else:
                options = [f"◽ {escape_markdown(option['text'])}" for option in submission.poll_data["options"]]
                embed.add_field(name="Poll", value="\n".join(options), inline=False)

        msg = await self.get_channel(lc_config["reposts_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.mail()
    async def handle_mail(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["mail_channel"]).send(embed=embed)
        await item.add_reactions(msg)

    @EventHandler.reports()
    async def handle_reports(self, item: RedditItem):
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["reports_channel"]).send(embed=embed)
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
