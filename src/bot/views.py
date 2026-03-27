"""
Discord interactive views for permission relay.

Provides Approve/Deny buttons that relay agent permission prompts
to the Discord user and wait for their response.
"""

import asyncio
import logging
import discord
from src.config import settings

logger = logging.getLogger(__name__)


class PermissionView(discord.ui.View):
    """Discord button view for Approve/Deny permission decisions.

    Only the original task owner can interact with the buttons.
    Auto-denies after timeout.
    """

    def __init__(self, user_id: int, timeout: float | None = None):
        super().__init__(timeout=timeout if timeout is not None else settings.agent_permission_timeout)
        self.user_id = user_id
        self.result: bool | None = None
        self._event = asyncio.Event()
        self.message: discord.Message | None = None  # Set after send for timeout cleanup

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the task owner can respond to this.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        self._event.set()
        await interaction.response.edit_message(
            content=interaction.message.content + "\n\n✅ **Approved**",
            view=None,
        )

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="❌")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        self._event.set()
        await interaction.response.edit_message(
            content=interaction.message.content + "\n\n❌ **Denied**",
            view=None,
        )

    async def on_timeout(self):
        self.result = False  # Auto-deny on timeout
        self._event.set()
        logger.info(f"Permission prompt timed out for user {self.user_id}, auto-denied")
        # Remove buttons from the message on timeout
        if self.message:
            try:
                await self.message.edit(
                    content=self.message.content.split("\n_Approve")[0]
                    + "\n\n⏰ **Denied (timeout)**",
                    view=None,
                )
            except Exception:
                pass  # Message may have been deleted

    async def wait_for_response(self) -> bool:
        """Block until user clicks a button or timeout expires."""
        await self._event.wait()
        return self.result


class PermissionRelay:
    """Relays permission requests from agent process to Discord.

    Sends a message with Approve/Deny buttons to the Discord channel
    and waits for the user's response. Returns True (approved) or
    False (denied/timed out).
    """

    def __init__(self, channel: discord.TextChannel, user_id: int, session_id: str):
        self.channel = channel
        self.user_id = user_id
        self.session_id = session_id
        self._request_count = 0

    async def request_permission(self, description: str) -> bool:
        """Send permission request to Discord and wait for user response.

        Args:
            description: The permission prompt text from the agent.

        Returns:
            True if approved, False if denied or timed out.
        """
        self._request_count += 1

        # Truncate description for Discord message limit
        if len(description) > 1500:
            description = description[-1500:]

        view = PermissionView(user_id=self.user_id)
        msg = await self.channel.send(
            f"🔐 **Permission Required** `[{self.session_id}]` (#{self._request_count})\n"
            f"```\n{description}\n```\n"
            f"_Approve or Deny within {int(settings.agent_permission_timeout)}s (auto-deny on timeout)_",
            view=view,
        )
        view.message = msg  # Enable timeout cleanup in on_timeout()

        result = await view.wait_for_response()

        logger.info(f"[{self.session_id}] Permission #{self._request_count}: {'approved' if result else 'denied'}")
        return result
