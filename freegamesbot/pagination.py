from __future__ import annotations

import discord


class EmbedPaginator(discord.ui.View):
    def __init__(self, embeds, user_id: int, urls=None, *, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.user_id = user_id
        self.urls = urls or [None] * len(embeds)

        self.current = 0
        self.message: discord.Message | None = None

        initial_url = next((url for url in self.urls if url), "https://discord.com")

        self.link_button = discord.ui.Button(
            label="Open", style=discord.ButtonStyle.link, row=0, url=initial_url
        )
        self.add_item(self.link_button)

        self._sync_state()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the command invoker can use these buttons.", ephemeral=True
            )
            return False
        return True

    def _sync_state(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                # Link buttons have no custom_id
                if child.custom_id == "prev":
                    child.disabled = self.current <= 0
                elif child.custom_id == "next":
                    child.disabled = self.current >= len(self.embeds) - 1
                elif child.style == discord.ButtonStyle.link:
                    url = self.urls[self.current]
                    if url:
                        child.url = url
                        child.disabled = False
                    else:
                        child.disabled = True

    @discord.ui.button(
        label="Prev", style=discord.ButtonStyle.secondary, custom_id="prev"
    )
    async def prev_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.current = max(0, self.current - 1)
        self._sync_state()
        await interaction.response.edit_message(
            embed=self.embeds[self.current], view=self
        )

    @discord.ui.button(
        label="Next", style=discord.ButtonStyle.primary, custom_id="next"
    )
    async def next_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.current = min(len(self.embeds) - 1, self.current + 1)
        self._sync_state()
        await interaction.response.edit_message(
            embed=self.embeds[self.current], view=self
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
