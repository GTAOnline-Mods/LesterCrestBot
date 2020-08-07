import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from discord.utils import escape_markdown

if TYPE_CHECKING:
    from ..lester import LesterCrest


class ModCog(commands.Cog):
    def __init__(self, bot: 'LesterCrest'):
        self.bot = bot
        self.stats_updated = None
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    @commands.command(help="Reload all the reactions for the subreddit configured and create a new info embed.")
    async def reload(self, ctx: commands.Context):
        await ctx.message.delete()

        channel = self.bot.get_channel(734713971428425729)
        message = await channel.fetch_message(736613065889546321)
        for sub in self.bot.subreddits:
            await sub.load_reactions()
            embed = await sub.get_reactions_embed(embed_template=self.bot.embed)
            await message.edit(embed=embed)
        await ctx.send("Reloaded all subreddit reactions!", delete_after=3)

    @tasks.loop(seconds=5 * 60.0)
    async def update_stats(self):
        await self.bot.wait_until_ready()

        if not self.bot.stats_updated:
            return

        self.bot.stats_updated = False

        channel = self.bot.get_channel(734713971428425729)
        message = await channel.fetch_message(738713709869793291)

        embed = self.bot.embed.set_author(name="Actions by Moderators")

        start_time = time.time()
        for t, users in self.bot.action_stats.items():
            user_stats = {k: v for k, v in sorted(users.items(), key=lambda item: item[1], reverse=True)}
            lines = [f"{escape_markdown(user)}: {actions}" for user, actions in user_stats.items()]
            embed.add_field(name=t.title(), value="\n".join(lines))

        await message.edit(embed=embed)


def setup(bot: 'LesterCrest'):
    bot.add_cog(ModCog(bot))
