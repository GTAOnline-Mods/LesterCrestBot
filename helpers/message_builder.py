import discord
from banhammer.models import MessageBuilder, RedditItem


class MessageBuilder(MessageBuilder):

    async def get_item_embed(self, item: RedditItem, embed_color: discord.Color = None):
        embed = await super().get_item_embed(item, embed_color=embed_color)

        if item.type in ["submission", "comment"] and item.source == "reports":
            embed.description += f"\nScore: `{item.item.score}`"

        return embed
