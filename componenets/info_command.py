import discord


class InfoView(discord.ui.DesignerView):
    def __init__(self, created_at):
        super().__init__()

        container = discord.ui.Container()
        action_row = discord.ui.ActionRow()

        container.add_text("## Application Info")
        container.add_text(
            "A Discord Bot To Send Notifications\n**When A New Free Game Drops**"
        )

        container.add_separator()

        container.add_text("### Links")
        container.add_text(
            "- [Terms](https://spreadsheets600.buzz) \n- [Link](https://spreadsheets600.buzz)"
        )

        container.add_separator()

        container.add_text("### Developer")
        container.add_text("`SpreadSheets600`")

        container.add_separator()

        container.add_text("### Created At")
        container.add_text(f"{created_at}")

        action_row.add_button(
            label="Invite Me",
            style=discord.ButtonStyle.link,
            url="https://spreadsheets600.buzz",
        )

        action_row.add_button(
            label="GitHub",
            style=discord.ButtonStyle.link,
            url="https://github.com/spreadsheets600/free-games-bot",
        )

        self.add_item(container)
        self.add_item(action_row)
