import discord
from banhammer.models import MessageBuilder, RedditItem


class MessageBuilder(MessageBuilder):

    async def get_item_embed(self, item: RedditItem, *args, **kwargs):
        embed = await super().get_item_embed(item, *args, **kwargs)

        if item.type in ["submission", "comment"] and item.source == "reports":
            embed.description += f"\nScore: `{item.item.score}`"

        return embed
