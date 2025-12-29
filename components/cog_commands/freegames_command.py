import discord
from datetime import datetime

from utilities.tools import get_game_platform


class GiveawayView(discord.ui.DesignerView):
    def __init__(self, giveaway_data, giveaway_id, error=None):
        super().__init__()

        container = discord.ui.Container()
        action_row = discord.ui.ActionRow()

        if error is not None:
            container.add_text(f"### Error : \n```{error}```")

        elif giveaway_data is None:
            container.add_text(f"### No Giveaway Data Available For `{giveaway_id}`")

        else:
            media_gallery = discord.ui.MediaGallery()

            platform_url = get_game_platform(giveaway_data.get("platforms", ""))

            end_date_str = giveaway_data["end_date"].replace(" ", "T")
            end_date_dt = datetime.fromisoformat(end_date_str)

            end_date_ts = f"<t:{int(end_date_dt.timestamp())}:R>"

            if platform_url:
                thumbnail = discord.ui.Thumbnail(url=platform_url)
                header_section = discord.ui.Section(accessory=thumbnail)

                header_section.add_text(
                    f"## {giveaway_data['title'].split('(')[0]}\n### **Ends in** {end_date_ts}"
                )

                container.add_item(header_section)
            else:
                container.add_text(f"## {giveaway_data['title'].split('(')[0]}")

                container.add_separator()

                container.add_text(
                    f"## {giveaway_data['title'].split('(')[0]}\n### **Ends in** {end_date_ts}"
                )

            action_row.add_button(
                label=f"{giveaway_data['type']}",
                style=discord.ButtonStyle.primary,
                disabled=True,
            )

            action_row.add_button(
                label=f"{giveaway_data['worth']}",
                style=discord.ButtonStyle.danger,
                disabled=True,
            )

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
        if action_row.children:
            self.add_item(action_row)
