import logging
import discord
from src.agent.session import SessionManager, SessionStatus
from src.agent.output_parser import OutputParser

logger = logging.getLogger(__name__)

_STATUS_EMOJI = {
    SessionStatus.PENDING: "🕐",
    SessionStatus.RUNNING: "⏳",
    SessionStatus.DONE: "✅",
    SessionStatus.FAILED: "❌",
    SessionStatus.CANCELLED: "🚫",
}

_STATUS_LABEL = {
    SessionStatus.PENDING: "Pending",
    SessionStatus.RUNNING: "Running",
    SessionStatus.DONE: "Done",
    SessionStatus.FAILED: "Failed",
    SessionStatus.CANCELLED: "Cancelled",
}


class StatusCommand:
    """
    /status
    Shows detailed status of the current active (PENDING/RUNNING) task.
    """

    def __init__(self, session_manager: SessionManager, parser: OutputParser):
        self.session_manager = session_manager
        self.parser = parser

    async def execute(self, message: discord.Message) -> None:
        session = await self.session_manager.get_active_by_user(message.author.id)
        if not session:
            await message.reply("No task in progress.\nUse `/list` to see recent task history.")
            return

        emoji = _STATUS_EMOJI.get(session.status, "❓")
        label = _STATUS_LABEL.get(session.status, "Unknown")
        prompt_preview = session.prompt[:100] + ("..." if len(session.prompt) > 100 else "")

        lines = [
            f"{emoji} **{label}** `[{session.session_id}]` _{session.elapsed}_",
            f"",
            f"**Task**: {prompt_preview}",
        ]

        if session.progress:
            progress = session.progress[-500:] if len(session.progress) > 500 else session.progress
            if len(session.progress) > 500:
                progress = "..." + progress
            lines.append(f"\n**Recent output**:\n```\n{progress}\n```")

        await message.reply("\n".join(lines))
        logger.debug(f"/status | user={message.author.id} session={session.session_id}")


class CancelCommand:
    """
    /cancel
    Cancels the current active (PENDING/RUNNING) task.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def execute(self, message: discord.Message) -> None:
        session = await self.session_manager.get_active_by_user(message.author.id)
        if not session:
            await message.reply("No task to cancel.")
            return
        session.cancel()
        logger.info(f"/cancel | user={message.author.id} session={session.session_id}")
        await message.reply(f"🚫 Task `[{session.session_id}]` cancelled")


class ListCommand:
    """
    /list
    Shows recent task history (up to 10).
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def execute(self, message: discord.Message) -> None:
        sessions = await self.session_manager.get_recent_by_user(message.author.id, limit=10)
        if not sessions:
            await message.reply("No task history.")
            return

        lines = ["**📋 Recent Task History**\n"]
        for s in sessions:
            emoji = _STATUS_EMOJI.get(s.status, "❓")
            label = _STATUS_LABEL.get(s.status, "?")
            prompt_short = s.prompt[:60] + ("..." if len(s.prompt) > 60 else "")
            time_str = s.started_at.strftime("%H:%M:%S")
            lines.append(f"{emoji} `[{s.session_id}]` {label} _{s.elapsed}_ ({time_str})")
            lines.append(f"   {prompt_short}")

        await message.reply("\n".join(lines))
        logger.debug(f"/list | user={message.author.id} count={len(sessions)}")
