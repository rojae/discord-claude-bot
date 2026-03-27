import logging
import discord
from src.commands.task import TaskCommand
from src.commands.status_cancel import StatusCommand, CancelCommand, ListCommand
from src.commands.finance import FinanceCommand
from src.commands.admin import BanCommand, UnbanCommand, AllowCommand, DisallowCommand, BanListCommand, UserListCommand
from src.config import settings

logger = logging.getLogger(__name__)

_P = settings.command_prefix  # Command prefix shorthand

HELP_TEXT = f"""
**📋 Available Commands**

`{_P}task <prompt>` — Send a task to Claude Code
`{_P}status`        — Check current task status & progress
`{_P}cancel`        — Cancel the running task
`{_P}list`          — Recent task history (up to 10)
`{_P}finance`       — 코스피/코스닥/환율 시세 조회
`{_P}userlist`      — 유저 목록 조회
`{_P}help`          — Show this help message

**🔧 Admin Commands** (관리자 전용)
`{_P}ban <user_id> [일수]` — 유저 밴 (기본: 1000년)
`{_P}unban <user_id>`      — 유저 밴 해제
`{_P}allow <user_id>`      — 유저 허용 목록 추가
`{_P}disallow <user_id>`   — 유저 허용 목록 제거
`{_P}banlist`              — 밴/허용 현황 조회

**💬 Follow-up Conversation**
Reply to any bot result message to continue the conversation.
The bot will use `--continue` to resume context from the previous task.

**Examples**
```
{_P}task Review the auth logic in UserService
{_P}task Optimize the SQL stored procedure
{_P}task Update README.md
```
"""


class CommandRegistry:
    """Parses messages and routes them to the appropriate command handler."""

    def __init__(
        self,
        task_cmd: TaskCommand,
        status_cmd: StatusCommand,
        cancel_cmd: CancelCommand,
        list_cmd: ListCommand,
        finance_cmd: FinanceCommand,
        ban_cmd: BanCommand,
        unban_cmd: UnbanCommand,
        allow_cmd: AllowCommand,
        disallow_cmd: DisallowCommand,
        banlist_cmd: BanListCommand,
        userlist_cmd: UserListCommand,
    ):
        self.task_cmd = task_cmd
        self.status_cmd = status_cmd
        self.cancel_cmd = cancel_cmd
        self.list_cmd = list_cmd
        self.finance_cmd = finance_cmd
        self.ban_cmd = ban_cmd
        self.unban_cmd = unban_cmd
        self.allow_cmd = allow_cmd
        self.disallow_cmd = disallow_cmd
        self.banlist_cmd = banlist_cmd
        self.userlist_cmd = userlist_cmd

    async def dispatch(self, message: discord.Message):
        content = message.content.strip()
        p = settings.command_prefix

        logger.debug(f"dispatch | user={message.author.id} | content={content[:80]!r}")

        # Extract command name (case-insensitive)
        if not content.startswith(p):
            return
        cmd_body = content[len(p):]
        cmd_name = cmd_body.split()[0].lower() if cmd_body.split() else ""

        if cmd_name == "task":
            prompt = cmd_body[len("task"):].strip()
            await self.task_cmd.execute(message, prompt)

        elif cmd_name == "status":
            await self.status_cmd.execute(message)

        elif cmd_name == "cancel":
            await self.cancel_cmd.execute(message)

        elif cmd_name == "list":
            await self.list_cmd.execute(message)

        elif cmd_name == "finance":
            await self.finance_cmd.execute(message)

        elif cmd_name == "ban":
            args = cmd_body[len("ban"):].strip()
            await self.ban_cmd.execute(message, args)

        elif cmd_name == "unban":
            args = cmd_body[len("unban"):].strip()
            await self.unban_cmd.execute(message, args)

        elif cmd_name == "allow":
            args = cmd_body[len("allow"):].strip()
            await self.allow_cmd.execute(message, args)

        elif cmd_name == "disallow":
            args = cmd_body[len("disallow"):].strip()
            await self.disallow_cmd.execute(message, args)

        elif cmd_name == "banlist":
            await self.banlist_cmd.execute(message)

        elif cmd_name == "userlist":
            await self.userlist_cmd.execute(message)

        elif cmd_name == "help":
            await message.reply(HELP_TEXT)

        else:
            await message.reply(
                f"Unknown command `{p}{cmd_name}`. "
                f"Use `{p}help` to see available commands."
            )
