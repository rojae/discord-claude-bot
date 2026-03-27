import asyncio
import logging
import signal
from src.config import settings
from src.logging_fmt import ColorFormatter, print_banner, print_config_table
from src.security.guard import SecurityGuard
from src.agent.session import SessionManager
from src.agent.runner import AgentRunner
from src.agent.output_parser import OutputParser
from src.commands.task import TaskCommand
from src.commands.status_cancel import StatusCommand, CancelCommand, ListCommand
from src.commands.finance import FinanceCommand
from src.commands.admin import BanCommand, UnbanCommand, AllowCommand, DisallowCommand, BanListCommand, UserListCommand
from src.commands.registry import CommandRegistry
from src.bot.client import BotClient

# Expired session cleanup interval (seconds)
_CLEANUP_INTERVAL = 300


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(level)


async def cleanup_loop(session_manager: SessionManager) -> None:
    """Periodically removes expired sessions from memory."""
    logger = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        removed = await session_manager.cleanup_expired()
        if removed:
            logger.info(f"Cleaned up {removed} expired session(s)")


async def main_async() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    # Print startup banner
    print_banner()

    # Dependency injection
    guard = SecurityGuard()
    session_manager = SessionManager()
    parser = OutputParser()
    runner = AgentRunner(session_manager)

    # Create bot early so commands can reference it
    bot = BotClient(None, guard)  # registry set below

    task_cmd = TaskCommand(runner, parser, guard)
    status_cmd = StatusCommand(session_manager, parser)
    cancel_cmd = CancelCommand(session_manager)
    list_cmd = ListCommand(session_manager)
    finance_cmd = FinanceCommand()
    ban_cmd = BanCommand(guard)
    unban_cmd = UnbanCommand(guard)
    allow_cmd = AllowCommand(guard)
    disallow_cmd = DisallowCommand(guard)
    banlist_cmd = BanListCommand(guard)
    userlist_cmd = UserListCommand(guard, bot)
    registry = CommandRegistry(
        task_cmd, status_cmd, cancel_cmd, list_cmd, finance_cmd,
        ban_cmd, unban_cmd, allow_cmd, disallow_cmd, banlist_cmd, userlist_cmd,
    )

    bot.registry = registry

    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_loop(session_manager))

    # Graceful shutdown via SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received, closing gracefully...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        # Start bot in background and wait for shutdown signal
        bot_task = asyncio.create_task(bot.start(settings.discord_token))
        await shutdown_event.wait()
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await bot.close()
        logger.info("Bot shutdown complete")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
