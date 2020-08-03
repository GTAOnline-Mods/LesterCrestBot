import discord
from discord.ext import commands


class ModCog(commands.Cog):
    def __init__(self, bot: 'Lester'):
        self.bot = bot

    @commands.command(help="Reload all the reactions for the subreddit configured and create a new info embed.")
    async def reload(self, ctx: commands.Context):
        await ctx.message.delete()

        channel = bot.get_channel(734713971428425729)
        message = await channel.fetch_message(736613065889546321)
        for sub in bot.subreddits:
            await sub.load_reactions()
            embed = await sub.get_reactions_embed(embed_template=bot.embed)
            await message.edit(embed=embed)
        await ctx.send("Reloaded all subreddit reactions!", delete_after=3)


def setup(bot: 'Lester'):
    bot.add_cog(ModCog(bot))
