import discord


class PingView(discord.ui.DesignerView):
    def __init__(
        self,
        uptime,
        latency,
    ):
        super().__init__()

        container = discord.ui.Container()

        container.add_text("### :ping_pong: Pong !")

        container.add_separator()

        container.add_text(uptime)
        container.add_text(latency)

        self.add_item(container)
