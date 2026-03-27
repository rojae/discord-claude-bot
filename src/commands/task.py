import asyncio
import io
import logging
import discord
from src.agent.runner import AgentRunner
from src.agent.output_parser import OutputParser
from src.agent.session import Session, TERMINAL_STATUSES
from src.config import settings
from src.security.guard import SecurityGuard

logger = logging.getLogger(__name__)

# File fallback threshold (with buffer below Discord message limit)
_FILE_FALLBACK_THRESHOLD = settings.discord_message_limit - 100

# Seconds between Discord progress message edits
_PROGRESS_INTERVAL = 5


class TaskCommand:
    """
    /task <prompt>
    Sends a task to the AI agent CLI and returns the result to Discord.
    """

    def __init__(self, runner: AgentRunner, parser: OutputParser, guard: SecurityGuard):
        self.runner = runner
        self.parser = parser
        self.guard = guard

    async def execute(self, message: discord.Message, prompt: str) -> None:
        if not prompt.strip():
            await message.reply("Usage: `/task <prompt>`")
            return

        # Block dangerous commands
        warning = self.guard.check_dangerous_prompt(prompt)
        if warning:
            await message.reply(warning)
            return

        if await self._check_active_task(message):
            return

        permission_handler = self._create_permission_handler(message)

        session = await self.runner.run(
            prompt, message.author.id, message.channel.id,
            permission_handler=permission_handler,
        )

        if permission_handler:
            permission_handler.session_id = session.session_id

        reply = await message.reply(self.parser.format_start(session))
        logger.info(f"[{session.session_id}] Reply message sent")

        await self._poll_and_finalize(message, reply, session)

    async def execute_followup(self, message: discord.Message, prompt: str,
                               original_session: Session) -> None:
        """Execute a follow-up task that continues a previous conversation."""
        # Block dangerous commands
        warning = self.guard.check_dangerous_prompt(prompt)
        if warning:
            await message.reply(warning)
            return

        if await self._check_active_task(message):
            return

        permission_handler = self._create_permission_handler(message)

        session = await self.runner.run(
            prompt, message.author.id, message.channel.id,
            permission_handler=permission_handler,
            continue_mode=True,
        )

        if permission_handler:
            permission_handler.session_id = session.session_id

        reply = await message.reply(
            self.parser.format_start(session, label="Follow-up started")
        )
        logger.info(
            f"[{session.session_id}] Follow-up reply sent "
            f"(continuing from [{original_session.session_id}])"
        )

        await self._poll_and_finalize(message, reply, session)

    # ── Private helpers ──────────────────────────────────────────

    async def _check_active_task(self, message: discord.Message) -> bool:
        """Check if user has reached max concurrent tasks. Returns True if blocked."""
        count = await self.runner.session_manager.count_active_by_user(message.author.id)
        max_per_user = settings.agent_max_per_user
        if count >= max_per_user:
            await message.reply(
                f"동시 작업 한도에 도달했습니다 ({count}/{max_per_user})\n"
                f"`/cancel`로 진행 중인 작업을 취소하거나 완료를 기다려주세요."
            )
            return True
        return False

    def _create_permission_handler(self, message: discord.Message):
        """Create a permission handler for relay mode, or None."""
        if not settings.is_permission_relay:
            return None
        from src.bot.views import PermissionRelay
        return PermissionRelay(
            channel=message.channel,
            user_id=message.author.id,
            session_id="...",
        )

    async def _poll_and_finalize(self, message: discord.Message,
                                 reply: discord.Message, session: Session) -> None:
        """Poll for task completion with progress updates, then finalize output."""
        ticks = 0.0
        last_edit_content = ""
        while session.status not in TERMINAL_STATUSES:
            await asyncio.sleep(settings.poll_interval_seconds)
            ticks += settings.poll_interval_seconds
            if ticks >= _PROGRESS_INTERVAL:
                ticks = 0.0
                preview = self.parser.format_progress(session)
                if preview != last_edit_content:
                    last_edit_content = preview
                    try:
                        await reply.edit(content=preview)
                    except Exception:
                        pass  # Ignore Discord rate limit errors

        result_text = self.parser.format_result(session)

        if len(result_text) > _FILE_FALLBACK_THRESHOLD:
            file = discord.File(
                fp=io.BytesIO(session.output.encode()),
                filename=f"result_{session.session_id}.txt",
            )
            sent = await message.channel.send(
                f"**Done** `[{session.session_id}]` _{session.elapsed}_ "
                f"— Output too long, sent as file.",
                file=file,
            )
            session.reply_message_id = sent.id
            try:
                await reply.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except Exception:
                logger.debug(f"[{session.session_id}] Failed to delete progress message")
        else:
            try:
                await reply.edit(content=result_text)
            except discord.NotFound:
                # Original reply was deleted — send a new message
                reply = await message.channel.send(result_text)
            session.reply_message_id = reply.id
