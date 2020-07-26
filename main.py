import configparser
import logging

import apraw
import banhammer
import discord
from banhammer.models import Subreddit
from discord.ext import commands

from cmds import HelpCommand
from config import config as lc_config

logger = logging.getLogger("banhammer")

formatter = logging.Formatter(u'%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# use StreamHandler for console output
fileHandle = logging.FileHandler('banhammer.log')
fileHandle.setFormatter(formatter)
logger.addHandler(fileHandle)


bot = commands.Bot(
    lc_config["command_prefix"],
    description="/r/gtaonline's moderation bot using Banhammer.py.",
    help_command=HelpCommand(discord.Colour(0).from_rgb(207, 226, 206)))

bh = banhammer.Banhammer(
    apraw.Reddit("LCB"),
    bot=bot,
    change_presence=lc_config["change_presence"],
    embed_color=discord.Colour(0).from_rgb(207, 226, 206))


@bot.event
async def on_command_error(ctx, error):
    print(error)


@bot.event
async def on_ready():
    print(str(bot.user) + ' is running.')

    for sub in lc_config["subreddits"]:
        s = Subreddit(bh, **sub)
        await s.load_reactions()
        await bh.add_subreddits(s)

    channel = bot.get_channel(734713971428425729)
    message = await channel.fetch_message(736613065889546321)
    await message.edit(embed=bh.get_reactions_embed())

    bh.run()


@bot.command()
async def reload(ctx):
    await ctx.message.delete()
    for sub in bh.subreddits:
        await sub.load_reactions()
    await ctx.send("Reloaded all subreddit reactions!", delete_after=3)

    channel = bot.get_channel(734713971428425729)
    message = await channel.fetch_message(736613065889546321)
    await message.edit(embed=bh.get_reactions_embed())


@bot.command()
async def subreddits(ctx):
    await ctx.send(embed=bh.get_subreddits_embed())


@bot.command()
async def reactions(ctx):
    await ctx.send(embed=bh.get_reactions_embed())


@bh.new()
async def handle_new(p):
    msg = await bot.get_channel(lc_config["new_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bh.comments()
async def handle_comments(p):
    author_name = await p.get_author_name()
    if author_name.lower() in ["automoderator", "lestercrestbot"]:
        return
    msg = await bot.get_channel(lc_config["comments_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bh.mail()
async def handle_mail(p):
    msg = await bot.get_channel(lc_config["mail_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bh.queue()
async def handle_queue(p):
    msg = await bot.get_channel(lc_config["queue_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bh.reports()
async def handle_reports(p):
    msg = await bot.get_channel(lc_config["reports_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bh.mod_actions()
async def handle_actions(p):
    msg = await bot.get_channel(lc_config["actions_channel"]).send(embed=await p.get_embed())
    for react in p.get_reactions():
        await msg.add_reaction(react.emoji)


@bot.event
async def on_message(m):
    if m.author.bot:
        return

    item = await bh.get_item(m.content)
    if item:
        for react in item.get_reactions():
            await m.add_reaction(react.emoji)

    await bot.process_commands(m)


@bot.event
async def on_raw_reaction_add(p):
    c = bot.get_channel(p.channel_id)

    u = c.guild.get_member(p.user_id)
    if u.bot:
        return

    m = await c.fetch_message(p.message_id)
    e = p.emoji.name if not p.emoji.is_custom_emoji() else f"<:{p.emoji.name}:{p.emoji.id}>"

    item = await bh.get_item(m.embeds[0] if m.embeds else m.content)
    if not item:
        return

    reaction = item.get_reaction(e)
    if not reaction:
        return

    try:
        await m.delete()
        result = await reaction.handle(item, user=u.nick)
        channel = bot.get_channel(lc_config["approved_channel"] if result.approved else lc_config["removed_channel"])
        await channel.send(embed=await result.get_embed())
    except Exception as e:
        print(e)


config = configparser.ConfigParser()
config.read("discord.ini")
bot.run(config["LCB"]["token"])
