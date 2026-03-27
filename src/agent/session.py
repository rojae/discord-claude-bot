import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from src.config import settings

# How long to keep completed sessions in memory (default 30 min for follow-up support)
_SESSION_TTL_SECONDS = settings.session_ttl_seconds


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Terminal statuses (polling exit condition)
TERMINAL_STATUSES = frozenset({SessionStatus.DONE, SessionStatus.FAILED, SessionStatus.CANCELLED})

# Active statuses (duplicate execution guard)
ACTIVE_STATUSES = frozenset({SessionStatus.PENDING, SessionStatus.RUNNING})


@dataclass
class Session:
    session_id: str
    prompt: str
    user_id: int
    channel_id: int
    status: SessionStatus = SessionStatus.PENDING
    output: str = ""
    error: str = ""
    progress: str = ""  # Real-time progress (accumulated stdout)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = field(default=None)
    reply_message_id: Optional[int] = field(default=None)  # Discord message ID for follow-up replies
    # Exclude process from dataclass comparison/repr
    process: Optional[asyncio.subprocess.Process] = field(default=None, compare=False, repr=False)

    def finish(self, output: str) -> None:
        self.status = SessionStatus.DONE
        self.output = output
        self.finished_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        self.status = SessionStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        self.status = SessionStatus.CANCELLED
        self.finished_at = datetime.now(timezone.utc)
        if self.process and self.process.returncode is None:
            self.process.terminate()

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def elapsed(self) -> str:
        end = self.finished_at or datetime.now(timezone.utc)
        secs = int((end - self.started_at).total_seconds())
        return f"{secs}s"

    @property
    def is_expired(self) -> bool:
        """Check if the completed session has exceeded its TTL."""
        if self.finished_at is None:
            return False
        return datetime.now(timezone.utc) - self.finished_at > timedelta(seconds=_SESSION_TTL_SECONDS)


class SessionManager:
    """Manages sessions in memory (asyncio-safe)."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create(self, session_id: str, prompt: str, user_id: int, channel_id: int) -> Session:
        session = Session(
            session_id=session_id,
            prompt=prompt,
            user_id=user_id,
            channel_id=channel_id,
        )
        async with self._lock:
            self._sessions[session_id] = session
        return session

    async def get(self, session_id: str) -> Optional[Session]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def get_active_by_user(self, user_id: int) -> Optional[Session]:
        """Returns the user's most recent active (PENDING/RUNNING) session, if any."""
        async with self._lock:
            for session in reversed(list(self._sessions.values())):
                if session.user_id == user_id and session.is_active:
                    return session
        return None

    async def count_active_by_user(self, user_id: int) -> int:
        """Returns the count of user's active (PENDING/RUNNING) sessions."""
        async with self._lock:
            return sum(
                1 for s in self._sessions.values()
                if s.user_id == user_id and s.is_active
            )

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def get_by_reply_message(self, message_id: int) -> Optional[Session]:
        """Returns the session linked to a specific Discord reply message ID."""
        async with self._lock:
            for session in reversed(list(self._sessions.values())):
                if session.reply_message_id == message_id:
                    return session
        return None

    async def get_recent_by_user(self, user_id: int, limit: int = 10) -> list[Session]:
        """Returns the user's recent sessions (newest first)."""
        async with self._lock:
            sessions = [s for s in self._sessions.values() if s.user_id == user_id]
            sessions.sort(key=lambda s: s.started_at, reverse=True)
            return sessions[:limit]

    async def cleanup_expired(self) -> int:
        """Removes expired sessions and returns the count removed."""
        async with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.is_expired]
            for sid in expired:
                del self._sessions[sid]
        return len(expired)
