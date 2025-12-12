from __future__ import annotations

import discord


class EmbedPaginator(discord.ui.View):
    def __init__(self, embeds, user_id: int, *, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.user_id = user_id
        self.current = 0
        self.message: discord.Message | None = None
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
                if child.custom_id == "prev":
                    child.disabled = self.current <= 0
                elif child.custom_id == "next":
                    child.disabled = self.current >= len(self.embeds) - 1

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
