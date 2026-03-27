import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import discord
from src.config import settings

logger = logging.getLogger(__name__)

# Dangerous commands that should be blocked from prompts
_DANGEROUS_PATTERNS = re.compile(
    r'\b('
    r'rm\s|rm$|rmdir|rm\b|'
    r'unlink\b|'
    r'shred\b|'
    r'mkfs\b|'
    r'dd\s+if=|'
    r'>\s*/dev/|'
    r'chmod\s+000|'
    r'chown\b.*/'
    r')\b',
    re.IGNORECASE,
)

KST = timezone(timedelta(hours=9))

# Persistent data file for runtime-managed bans and allowed users
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_FILE = _DATA_DIR / "security.json"

# Ban response message
BAN_RESPONSE = "읍읍"

# Default ban list (used on first run if no data file exists)
_DEFAULT_BANS: dict[str, str] = {}


def _load_data() -> dict:
    """Load persisted security data from JSON file."""
    if _DATA_FILE.exists():
        try:
            with open(_DATA_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load security data: {e}")
    return {}


def _save_data(data: dict) -> None:
    """Persist security data to JSON file."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class SecurityGuard:
    """Validates that only allowed users and channels can execute commands."""

    def __init__(self):
        stored = _load_data()

        # Load bans: stored data takes priority, otherwise use defaults
        raw_bans = stored.get("bans", _DEFAULT_BANS)
        self._bans: dict[int, datetime] = {}
        for uid_str, until_str in raw_bans.items():
            self._bans[int(uid_str)] = datetime.fromisoformat(until_str)

        # Load allowed users: stored data takes priority, otherwise use .env
        if "allowed_users" in stored:
            self._allowed_users: set[int] = set(stored["allowed_users"])
        else:
            self._allowed_users = set(settings.allowed_user_ids)

        self._persist()

    def _persist(self) -> None:
        """Save current state to disk."""
        data = {
            "bans": {
                str(uid): until.isoformat() for uid, until in self._bans.items()
            },
            "allowed_users": sorted(self._allowed_users),
        }
        _save_data(data)

    # ── Admin check ──────────────────────────────────────────

    def is_admin(self, user_id: int) -> bool:
        """Check if a user is an admin."""
        return user_id in settings.admin_user_ids

    # ── Ban management ───────────────────────────────────────

    def is_banned(self, user_id: int) -> bool:
        """Check if a user is currently banned."""
        if user_id not in self._bans:
            return False
        ban_until = self._bans[user_id]
        if datetime.now(KST) >= ban_until:
            return False
        return True

    def ban_user(self, user_id: int, until: datetime) -> None:
        """Ban a user until the specified datetime."""
        self._bans[user_id] = until
        self._persist()
        logger.info(f"User {user_id} banned until {until.isoformat()}")

    def unban_user(self, user_id: int) -> bool:
        """Unban a user. Returns True if user was banned."""
        if user_id in self._bans:
            del self._bans[user_id]
            self._persist()
            logger.info(f"User {user_id} unbanned")
            return True
        return False

    def get_ban_expiry(self, user_id: int) -> datetime | None:
        """Get ban expiry for a user, or None if not banned."""
        return self._bans.get(user_id)

    def get_all_bans(self) -> dict[int, datetime]:
        """Get all bans."""
        return dict(self._bans)

    # ── Allowed user management ──────────────────────────────

    def allow_user(self, user_id: int) -> None:
        """Add a user to the allowed list."""
        self._allowed_users.add(user_id)
        self._persist()
        logger.info(f"User {user_id} added to allowed list")

    def disallow_user(self, user_id: int) -> bool:
        """Remove a user from the allowed list. Returns True if user was in list."""
        if user_id in self._allowed_users:
            self._allowed_users.discard(user_id)
            self._persist()
            logger.info(f"User {user_id} removed from allowed list")
            return True
        return False

    def get_allowed_users(self) -> set[int]:
        """Get all allowed user IDs."""
        return set(self._allowed_users)

    # ── Message-level checks ─────────────────────────────────

    def is_allowed(self, message: discord.Message) -> bool:
        if message.guild is None:
            logger.debug(f"DM blocked | user={message.author.id}")
            return False
        return self._is_allowed_channel(message) and self._is_allowed_user(message)

    def _is_allowed_channel(self, message: discord.Message) -> bool:
        if not settings.allowed_channel_ids:
            return True
        if message.channel.id not in settings.allowed_channel_ids:
            logger.debug(f"Channel blocked | channel={message.channel.id} user={message.author.id}")
            return False
        return True

    def _is_allowed_user(self, message: discord.Message) -> bool:
        if not self._allowed_users:
            return True
        if message.author.id not in self._allowed_users:
            logger.debug(f"User blocked | user={message.author.id} channel={message.channel.id}")
            return False
        return True

    # ── Prompt security ──────────────────────────────────────

    def check_dangerous_prompt(self, prompt: str) -> str | None:
        """Check if a prompt contains dangerous commands."""
        match = _DANGEROUS_PATTERNS.search(prompt)
        if match:
            cmd = match.group(0).strip()
            logger.warning(f"Dangerous command blocked: {cmd!r} in prompt: {prompt[:80]!r}")
            return f"⛔ 보안 차단: `{cmd}` 명령어는 사용할 수 없습니다."
        return None
