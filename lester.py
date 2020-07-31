import asyncio
import configparser
import logging
import os
import pickle
from datetime import datetime

import apraw
import banhammer
import discord
from banhammer import Banhammer
from banhammer.models import EventHandler, ItemAttribute, RedditItem, Subreddit
from discord.ext import commands
from discord.ext.commands import Bot

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
        Banhammer.__init__(self, reddit, bot=self, embed_color=gta_green,
                           change_presence=lc_config["change_presence"])

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, discord.ext.commands.errors.CommandNotFound):
            pass
        else:
            print(f"Error in command: {error}")

    async def on_handler_error(self, error):
        print(f"Error in handler: {e}")

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

        msg = None
        if getattr(item.item, "approved_by",
                   None) and not reaction.approve and item.item.approved_by.lower() != "automoderator":
            msg = f"The submission by /u/{await item.get_author_name()} was already approved by /u/{item.item.approved_by}, are you sure you want to remove it?\n\n" \
                f"{item.url}"
        elif getattr(item.item, "removed_by_category", None) == "moderator" and reaction.approve and item.item.removed_by.lower() != "automoderator":
            msg = f"The submission by /u/{await item.get_author_name()} was already approved by /u/{item.item.removed_by}, are you sure you want to approve it?\n\n" \
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
        channel = self.get_channel(lc_config["approved_channel"] if result.approved else lc_config["removed_channel"])
        await channel.send(embed=await result.get_embed(embed_template=self.embed))
        await m.delete()

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
    @EventHandler.filter(ItemAttribute.AUTHOR, "automoderator", "lestercrestbot", reverse=True)
    async def handle_comments(self, item: RedditItem):
        author_name = await item.get_author_name()
        embed = await item.get_embed(embed_template=self.embed)
        msg = await self.get_channel(lc_config["comments_channel"]).send(embed=embed)
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


bot = LesterCrest()


@bot.command(help="Reload all the reactions for the subreddit configured and create a new info embed.")
async def reload(ctx: commands.Context):
    await ctx.message.delete()

    channel = bot.get_channel(734713971428425729)
    message = await channel.fetch_message(736613065889546321)
    for sub in bot.subreddits:
        await sub.load_reactions()
        embed = await sub.get_reactions_embed(embed_template=bot.embed)
        await message.edit(embed=embed)
    await ctx.send("Reloaded all subreddit reactions!", delete_after=3)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("discord.ini")
    bot.run(config["LCB"]["token"])
