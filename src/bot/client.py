import logging
from datetime import datetime, timezone
import discord
from src.commands.registry import CommandRegistry
from src.security.guard import SecurityGuard
from src.config import settings
from src.logging_fmt import print_config_table

logger = logging.getLogger(__name__)


class BotClient(discord.Client):

    def __init__(self, registry: CommandRegistry | None, guard: SecurityGuard):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.registry = registry
        self.guard = guard
        self._ready_at: datetime | None = None

    async def on_ready(self) -> None:
        self._ready_at = datetime.now(timezone.utc)
        logger.info(f"Connected as {self.user} (ID: {self.user.id})")
        print_config_table([
            ("Bot", f"{self.user}"),
            ("Prefix", settings.command_prefix),
            ("Agent", settings.agent_type),
            ("Permission", settings.agent_permission_mode),
            ("Working dir", settings.agent_working_dir),
            ("Channels", str(settings.allowed_channel_ids or "all")),
            ("Users", str(settings.allowed_user_ids or "all")),
            ("Timeout", f"{settings.agent_timeout}s"),
            ("Session TTL", f"{settings.session_ttl_seconds}s"),
            ("Skip missed", str(settings.skip_missed_messages)),
        ])

    def _strip_mention(self, content: str) -> str:
        """Strip bot mention prefix and return remaining content."""
        if self.user is None:
            return content
        for prefix in (f"<@{self.user.id}>", f"<@!{self.user.id}>"):
            if content.startswith(prefix):
                return content[len(prefix):].strip()
        return content

    def _is_mentioned(self, content: str) -> bool:
        """Check if the bot is mentioned in the content."""
        if self.user is None:
            return False
        return f"<@{self.user.id}>" in content or f"<@!{self.user.id}>" in content

    async def _is_reply_to_bot(self, message: discord.Message) -> bool:
        """Check if the message is a reply to one of the bot's messages."""
        if not message.reference or not message.reference.message_id:
            return False
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            return ref_msg.author == self.user
        except Exception:
            return False

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        content = message.content.strip()
        is_mentioned = self._is_mentioned(content)
        is_reply = await self._is_reply_to_bot(message) if message.reference else False

        # Only respond when bot is mentioned OR replying to a bot message
        if not is_mentioned and not is_reply:
            return

        # Skip messages that were queued while bot was offline
        if settings.skip_missed_messages and self._ready_at:
            msg_time = message.created_at.replace(tzinfo=timezone.utc) if message.created_at.tzinfo is None else message.created_at
            if msg_time < self._ready_at:
                logger.info(f"Skipping missed message | user={message.author.id} content={message.content[:50]!r}")
                return

        # Check ban list before processing
        if self.guard.is_banned(message.author.id):
            from src.security.guard import BAN_RESPONSE
            logger.info(f"Banned user responded | user={message.author.id}")
            await message.reply(BAN_RESPONSE)
            return

        if not self.guard.is_allowed(message):
            logger.debug(f"Denied | user={message.author.id} channel={message.channel.id}")
            return

        # Handle follow-up reply to bot result message
        if is_reply:
            followup_prompt = self._strip_mention(content) if is_mentioned else content
            if not followup_prompt.strip():
                return

            ref_message_id = message.reference.message_id
            session_mgr = self.registry.task_cmd.runner.session_manager
            original_session = await session_mgr.get_by_reply_message(ref_message_id)

            if original_session and original_session.user_id == message.author.id:
                logger.info(f"Follow-up reply detected | user={message.author.id} | original=[{original_session.session_id}]")
                await self.registry.task_cmd.execute_followup(
                    message, followup_prompt, original_session
                )
                return

            if original_session is None and not is_mentioned:
                # Reply to bot message but session expired — inform the user
                await message.reply(
                    "⏳ This conversation session has expired.\n"
                    f"Use `{settings.command_prefix}task <prompt>` to start a new task."
                )
                return

            # Reply to bot but no matching session and mentioned → fall through to normal handling

        content = self._strip_mention(content)

        if not content.startswith(settings.command_prefix):
            # Mention without command prefix → treat as /task
            if content:
                message.content = f"{settings.command_prefix}task {content}"
            else:
                return
        else:
            message.content = content

        await self.registry.dispatch(message)

    async def on_error(self, event: str, *args, **kwargs) -> None:
        logger.exception(f"Discord event error: {event}")
