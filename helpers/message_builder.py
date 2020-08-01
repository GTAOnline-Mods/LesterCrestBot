import discord
from discord import Embed
from banhammer.models import MessageBuilder, RedditItem


class MessageBuilder(MessageBuilder):

    async def get_item_embed(self, item: RedditItem, *args, **kwargs):
        embed = await super().get_item_embed(item, *args, **kwargs)

        if item.type in ["submission", "comment"] and item.source == "reports":
            txt = f"\nScore: `{item.item.score}`"
            embed.description = embed.description + txt if embed.description else txt

        return embed
