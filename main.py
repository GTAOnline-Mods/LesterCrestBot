import configparser
import logging
import os
import pickle
from datetime import datetime

import apraw
import banhammer
import discord
from banhammer.models import RedditItem, Subreddit
from discord.ext import commands

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


class LesterCrest(commands.Bot, banhammer.Banhammer):
    def __init__(self, **options):
        super().__init__(lc_config["command_prefix"], help_command=HelpCommand(gta_green),
                         description="/r/gtaonline's moderation bot using Banhammer.py.", **options)
        banhammer.Banhammer.__init__(self, reddit, bot=self, embed_color=gta_green,
                                     change_presence=lc_config["change_presence"])

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, discord.ext.commands.errors.CommandNotFound):
            pass
        else:
            print(error)

    async def on_ready(self):
        print(f"{self.user} is running.")

        for sub in lc_config["subreddits"]:
            s = Subreddit(self, **sub)
            await s.load_reactions()
            await self.add_subreddits(s)

        channel = self.get_channel(734713971428425729)
        message = await channel.fetch_message(736613065889546321)

        for sub in self.subreddits:
            embed = await sub.get_reactions_embed(embed_template=lester.embed)
            await message.edit(embed=embed)
            break

        self.run()

    async def on_message(self, message: discord.Message):
        if m.author.self:
            return

        item = await self.get_item(message.content)
        if item:
            await item.add_reactions(message)

        await self.process_commands(message)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        c = self.get_channel(payload.channel_id)

        u = c.guild.get_member(payload.user_id)
        if u.bot:
            return
        if not any(role.id == 734714209342062602 for role in u.roles):
            return

        m = await c.fetch_message(payload.message_id)
        e = payload.emoji.name if not payload.emoji.is_custom_emoji() else f"<:{payload.emoji.name}:{payload.emoji.id}>"

        item = await self.get_item(m.embeds[0] if m.embeds else m.content)
        if not item:
            return

        reaction = item.get_reaction(e)
        if not reaction:
            return

        await m.delete()
        result = await reaction.handle(item, user=u.nick)
        channel = self.get_channel(lc_config["approved_channel"] if result.approved else lc_config["removed_channel"])
        await channel.send(embed=await result.get_embed(embed_template=self.embed))

        with open(lc_config["payloads_file"], "ab+") as f:
            pickle.dump(result.to_dict(), f)

    @commands.command()
    async def reload(self, ctx: commands.Context):
        await ctx.message.delete()
        for sub in self.subreddits:
            await sub.load_reactions()
        await ctx.send("Reloaded all subreddit reactions!", delete_after=3)

        channel = self.get_channel(734713971428425729)
        message = await channel.fetch_message(736613065889546321)
        for sub in self.subreddits:
            embed = await sub.get_reactions_embed(embed_template=self.embed)
            await message.edit(embed=embed)
            break

    @commands.command()
    async def subreddits(self, ctx: commands.Context):
        await ctx.send(embed=self.get_subreddits_embed(embed_template=self.embed))

    @commands.command()
    async def reactions(self, ctx: commands.Context):
        await ctx.send(embed=self.get_reactions_embed(embed_template=self.embed))

    @property
    def embed(self):
        embed = discord.Embed(colour=gta_green)
        embed.set_footer(text="Lester Crest Bot", icon_url=self.user.avatar_url)
        embed.timestamp = datetime.now()
        return embed


lester = LesterCrest()


@lester.new()
async def handle_new(item: RedditItem):
    embed = await item.get_embed(embed_template=lester.embed)
    msg = await lester.get_channel(lc_config["new_channel"]).send(embed=embed)
    await item.add_reactions(msg)


@lester.comments()
async def handle_comments(item: RedditItem):
    author_name = await item.get_author_name()
    if author_name.lower() in ["automoderator", "lestercrestbot"]:
        return
    embed = await item.get_embed(embed_template=lester.embed)
    msg = await lester.get_channel(lc_config["comments_channel"]).send(embed=embed)
    await item.add_reactions(msg)


@lester.mail()
async def handle_mail(item: RedditItem):
    embed = await item.get_embed(embed_template=lester.embed)
    msg = await lester.get_channel(lc_config["mail_channel"]).send(embed=embed)
    await item.add_reactions(msg)


@lester.reports()
async def handle_reports(item: RedditItem):
    embed = await item.get_embed(embed_template=lester.embed)
    msg = await lester.get_channel(lc_config["reports_channel"]).send(embed=embed)
    await item.add_reactions(msg)


@lester.mod_actions()
async def handle_actions(item: RedditItem):
    embed = await item.get_embed(embed_template=lester.embed)
    msg = await lester.get_channel(lc_config["actions_channel"]).send(embed=embed)
    await item.add_reactions(msg)


config = configparser.ConfigParser()
config.read("discord.ini")
lester.run(config["LCB"]["token"])
