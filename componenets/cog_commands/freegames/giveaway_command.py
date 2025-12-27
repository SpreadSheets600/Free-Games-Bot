import discord


class GiveawayView(discord.ui.DesignerView):
    def __init__(self, giveaway_data, giveaway_id, error=None):
        super().__init__()

        container = discord.ui.Container()

        if error is not None:
            container.add_text(f"### Error : \n```{error}```")

        elif giveaway_data is None:
            container.add_text(f"### No Giveaway Data Available For `{giveaway_id}`")

        else:
            action_row = discord.ui.ActionRow()
            media_gallery = discord.ui.MediaGallery()
            
            thumbnail = discord.ui.Thumbnail(url=giveaway_data.get("image"))

            header_section = discord.ui.Section(accessory=thumbnail)

            header_section.add_text("### Giveaway Details")

            container.add_item(header_section)

            container.add_text(f"## {giveaway_data['title']}")

            container.add_separator()

            container.add_text(f"**Worth :** ~~${giveaway_data['worth']}~~ **FREE**")
            container.add_text(f"**Platform :** {giveaway_data['platforms']}")

            container.add_text(f"**Type :** {giveaway_data['type']}")
            container.add_text(f"**Ends :** {giveaway_data['end_date']}")

            action_row.add_button(
                label="View",
                style=discord.ButtonStyle.link,
                url=giveaway_data["open_giveaway_url"],
            )

            if giveaway_data.get("image"):
                media_gallery.add_item(url=giveaway_data["image"])

                container.add_item(media_gallery)

            container.add_separator()

            container.add_text(giveaway_data["instructions"])

        self.add_item(container)
        self.add_item(action_row)
