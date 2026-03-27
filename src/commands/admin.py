"""
Admin commands for managing bans and allowed users.

Only users in ADMIN_USER_IDS can use these commands.
"""

import logging
from datetime import datetime, timezone, timedelta

import discord
from src.security.guard import SecurityGuard, KST

logger = logging.getLogger(__name__)


def _require_admin(guard: SecurityGuard, message: discord.Message) -> bool:
    """Check if message author is admin. Returns True if NOT admin (blocked)."""
    if not guard.is_admin(message.author.id):
        return True
    return False


class BanCommand:
    """/ban <user_id> [days] — Ban a user (admin only). Default: 1000 years."""

    def __init__(self, guard: SecurityGuard):
        self.guard = guard

    async def execute(self, message: discord.Message, args: str) -> None:
        if _require_admin(self.guard, message):
            await message.reply("⛔ 권한이 없습니다. 관리자만 사용할 수 있습니다.")
            return

        parts = args.split()
        if not parts:
            await message.reply("사용법: `/ban <user_id> [일수]`\n예: `/ban 123456789 365`")
            return

        try:
            user_id = int(parts[0])
        except ValueError:
            await message.reply("⛔ 유효하지 않은 user_id입니다.")
            return

        # Default: 1000 years
        days = 365000
        if len(parts) >= 2:
            try:
                days = int(parts[1])
            except ValueError:
                await message.reply("⛔ 일수는 숫자여야 합니다.")
                return

        # Don't allow banning admins
        if self.guard.is_admin(user_id):
            await message.reply("⛔ 관리자는 밴할 수 없습니다.")
            return

        until = datetime.now(KST) + timedelta(days=days)
        self.guard.ban_user(user_id, until)

        await message.reply(
            f"🔨 유저 `{user_id}` 밴 완료\n"
            f"해제 일시: `{until.strftime('%Y-%m-%d %H:%M KST')}`"
        )
        logger.info(f"/ban | admin={message.author.id} target={user_id} days={days}")


class UnbanCommand:
    """/unban <user_id> — Unban a user (admin only)."""

    def __init__(self, guard: SecurityGuard):
        self.guard = guard

    async def execute(self, message: discord.Message, args: str) -> None:
        if _require_admin(self.guard, message):
            await message.reply("⛔ 권한이 없습니다. 관리자만 사용할 수 있습니다.")
            return

        args = args.strip()
        if not args:
            await message.reply("사용법: `/unban <user_id>`")
            return

        try:
            user_id = int(args.split()[0])
        except ValueError:
            await message.reply("⛔ 유효하지 않은 user_id입니다.")
            return

        if self.guard.unban_user(user_id):
            await message.reply(f"✅ 유저 `{user_id}` 밴 해제 완료")
        else:
            await message.reply(f"ℹ️ 유저 `{user_id}`는 밴 목록에 없습니다.")

        logger.info(f"/unban | admin={message.author.id} target={user_id}")


class AllowCommand:
    """/allow <user_id> — Add user to allowed list (admin only)."""

    def __init__(self, guard: SecurityGuard):
        self.guard = guard

    async def execute(self, message: discord.Message, args: str) -> None:
        if _require_admin(self.guard, message):
            await message.reply("⛔ 권한이 없습니다. 관리자만 사용할 수 있습니다.")
            return

        args = args.strip()
        if not args:
            await message.reply("사용법: `/allow <user_id>`")
            return

        try:
            user_id = int(args.split()[0])
        except ValueError:
            await message.reply("⛔ 유효하지 않은 user_id입니다.")
            return

        self.guard.allow_user(user_id)
        await message.reply(f"✅ 유저 `{user_id}` 허용 목록에 추가됨")
        logger.info(f"/allow | admin={message.author.id} target={user_id}")


class DisallowCommand:
    """/disallow <user_id> — Remove user from allowed list (admin only)."""

    def __init__(self, guard: SecurityGuard):
        self.guard = guard

    async def execute(self, message: discord.Message, args: str) -> None:
        if _require_admin(self.guard, message):
            await message.reply("⛔ 권한이 없습니다. 관리자만 사용할 수 있습니다.")
            return

        args = args.strip()
        if not args:
            await message.reply("사용법: `/disallow <user_id>`")
            return

        try:
            user_id = int(args.split()[0])
        except ValueError:
            await message.reply("⛔ 유효하지 않은 user_id입니다.")
            return

        # Don't allow removing admins
        if self.guard.is_admin(user_id):
            await message.reply("⛔ 관리자는 허용 목록에서 제거할 수 없습니다.")
            return

        if self.guard.disallow_user(user_id):
            await message.reply(f"✅ 유저 `{user_id}` 허용 목록에서 제거됨")
        else:
            await message.reply(f"ℹ️ 유저 `{user_id}`는 허용 목록에 없습니다.")

        logger.info(f"/disallow | admin={message.author.id} target={user_id}")


class BanListCommand:
    """/banlist — Show current bans and allowed users (admin only)."""

    def __init__(self, guard: SecurityGuard):
        self.guard = guard

    async def execute(self, message: discord.Message) -> None:
        if _require_admin(self.guard, message):
            await message.reply("⛔ 권한이 없습니다. 관리자만 사용할 수 있습니다.")
            return

        bans = self.guard.get_all_bans()
        allowed = self.guard.get_allowed_users()

        lines = ["**🔧 관리 현황**\n"]

        # Ban list
        lines.append("**🔨 밴 목록**")
        if bans:
            for uid, until in sorted(bans.items()):
                status = "🔴 활성" if self.guard.is_banned(uid) else "⚪ 만료"
                lines.append(f"  {status} `{uid}` → {until.strftime('%Y-%m-%d %H:%M KST')}")
        else:
            lines.append("  없음")

        lines.append("")

        # Allowed users
        lines.append("**✅ 허용 유저**")
        if allowed:
            for uid in sorted(allowed):
                admin_tag = " 👑" if self.guard.is_admin(uid) else ""
                lines.append(f"  `{uid}`{admin_tag}")
        else:
            lines.append("  제한 없음 (모든 유저 허용)")

        await message.reply("\n".join(lines))
        logger.info(f"/banlist | admin={message.author.id}")


class UserListCommand:
    """/userlist — Show allowed users with status (available to all)."""

    def __init__(self, guard: SecurityGuard, bot):
        self.guard = guard
        self.bot = bot

    async def execute(self, message: discord.Message) -> None:
        allowed = self.guard.get_allowed_users()

        lines = ["**👥 유저 목록**\n"]

        if not allowed:
            lines.append("제한 없음 (모든 유저 허용)")
        else:
            for uid in sorted(allowed):
                # Try to resolve Discord username
                user = self.bot.get_user(uid)
                name = user.display_name if user else "알 수 없음"

                tags = []
                if self.guard.is_admin(uid):
                    tags.append("👑 관리자")
                if self.guard.is_banned(uid):
                    expiry = self.guard.get_ban_expiry(uid)
                    until = expiry.strftime('%Y-%m-%d') if expiry else "?"
                    tags.append(f"🔨 밴 (~{until})")

                tag_str = f"  [{', '.join(tags)}]" if tags else ""
                lines.append(f"  `{uid}` **{name}**{tag_str}")

        lines.append(f"\n총 {len(allowed)}명")

        await message.reply("\n".join(lines))
        logger.info(f"/userlist | user={message.author.id}")
