from src.agent.session import Session, SessionStatus
from src.config import settings

# Max characters for prompt preview in format_start
_PROMPT_PREVIEW_LEN = 200

# Code block wrapping overhead: "```\n" (4) + "\n```" (4) = 8
_CODE_BLOCK_OVERHEAD = 8


def _sanitize_codeblock(text: str) -> str:
    """Escape triple backticks inside text to prevent breaking Discord markdown."""
    return text.replace("```", "``\u200b`")


class OutputParser:
    """Formats agent output into Discord messages."""

    def format_start(self, session: Session, label: str = "Task started") -> str:
        preview = _sanitize_codeblock(session.prompt[:_PROMPT_PREVIEW_LEN])
        suffix = "..." if len(session.prompt) > _PROMPT_PREVIEW_LEN else ""
        return (
            f"⚙️ **{label}** `[{session.session_id}]`\n"
            f"```\n{preview}{suffix}\n```"
        )

    def format_result(self, session: Session) -> str:
        if session.status == SessionStatus.DONE:
            output = self._truncate(session.output)
            if not output:
                return f"✅ **Done** `[{session.session_id}]` _{session.elapsed}_ (no output)"
            return (
                f"✅ **Done** `[{session.session_id}]` _{session.elapsed}_\n"
                f"{output}"
            )
        elif session.status == SessionStatus.FAILED:
            error = self._truncate(session.error) or "Unknown error"
            return (
                f"❌ **Failed** `[{session.session_id}]` _{session.elapsed}_\n"
                f"```\n{_sanitize_codeblock(error)}\n```"
            )
        elif session.status == SessionStatus.CANCELLED:
            return f"🚫 **Cancelled** `[{session.session_id}]`"
        else:
            return f"⏳ **In progress** `[{session.session_id}]` _{session.elapsed}_"

    def format_progress(self, session: Session) -> str:
        progress = session.progress
        if not progress:
            return f"⏳ **Working...** `[{session.session_id}]` _{session.elapsed}_"
        # Trim to fit Discord message limit, keeping the tail (most recent output)
        max_len = settings.agent_max_output - 150
        if len(progress) > max_len:
            progress = "..." + progress[-max_len:]
        return (
            f"⏳ **In progress** `[{session.session_id}]` _{session.elapsed}_\n"
            f"{progress}"
        )

    def _truncate(self, text: str) -> str:
        """Truncate text to fit within agent_max_output, accounting for code block wrapping."""
        limit = settings.agent_max_output - _CODE_BLOCK_OVERHEAD
        if len(text) <= limit:
            return text
        tail = "\n\n...(output truncated)"
        return text[: limit - len(tail)] + tail
