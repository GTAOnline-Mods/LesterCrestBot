import discord
from banhammer.models import MessageBuilder, RedditItem


class MessageBuilder(MessageBuilder):

    async def get_item_embed(self, item: RedditItem, embed_color: discord.Color = None):
        if item.type == "submission" and not item.item.is_self:
            embed = discord.Embed(
                colour=embed_color or item.subreddit.banhammer.embed_color
            )
            if item.source == "reports":
                title = f"{item.type.title()} reported on /r/{item.subreddit} by /u/{await item.get_author_name()}!"
            else:
                title = f"New {item.type} on /r/{item.subreddit} by /u/{await item.get_author_name()}!"
            embed.set_author(name=title, url=item.url or discord.Embed.Empty)
            embed.add_field(
                name="Title",
                value=discord.utils.escape_markdown(item.item.title),
                inline=False)
            if "i.redd.it" in item.item.url:
                embed.image.url = item.item.url
            else:
                embed.add_field(
                    name="URL",
                    value=discord.utils.escape_markdown(item.item.url),
                    inline=False)
            if item.source == "reports":
                embed.add_field(
                    name="Reports",
                    value="\n".join(f"{r[1]} {r[0]}" for r in item.item.user_reports),
                    inline=False)
            return embed
        else:
            return super().get_item_embed(item, embed_color=embed_color)
