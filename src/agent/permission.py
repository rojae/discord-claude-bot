"""
Permission detection for AI CLI agent stdout streams.

Detects permission prompts by combining regex pattern matching with
output stall detection. When the agent process stops producing output
and the recent buffer matches a permission pattern, a PermissionRequest
is emitted for relay to the user.
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# How many recent lines to check for permission patterns
_BUFFER_WINDOW = 10

# ANSI escape sequence pattern (colors, cursor movement, OSC sequences)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b\([A-Z]|\x1b[=>]')


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text.

    TUI-based agents (Claude Code, etc.) may emit ANSI codes for colors,
    cursor positioning, and terminal control. These must be stripped
    before regex pattern matching.
    """
    return _ANSI_RE.sub('', text)


@dataclass
class PermissionRequest:
    """A detected permission prompt from the agent's stdout."""

    description: str          # The permission prompt text (last N lines)
    matched_pattern: str      # The regex pattern that matched
    matched_line: str         # The specific line that matched


class PermissionDetector:
    """Detects permission prompts in agent stdout output.

    Uses compiled regex patterns from the agent preset to scan
    recent output lines. Called when stdout stalls (no new output
    for stall_timeout seconds), indicating the process may be
    waiting for user input.
    """

    def __init__(self, patterns: list[str]):
        self._compiled = []
        for pattern in patterns:
            try:
                self._compiled.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Invalid permission pattern '{pattern}': {e}")

    def detect(self, buffer: list[str]) -> PermissionRequest | None:
        """Check recent buffer lines for permission prompt patterns.

        Args:
            buffer: All stdout lines accumulated so far.

        Returns:
            PermissionRequest if a permission prompt is detected, None otherwise.
        """
        if not buffer or not self._compiled:
            return None

        # Only check the last N lines
        window = buffer[-_BUFFER_WINDOW:]

        for line in reversed(window):
            stripped = _strip_ansi(line.strip())
            if not stripped:
                continue
            for pattern in self._compiled:
                if pattern.search(stripped):
                    # Build context: show the last few lines for user clarity
                    context_lines = [_strip_ansi(l.strip()) for l in window if l.strip()]
                    description = "\n".join(context_lines[-5:])
                    logger.info(f"Permission prompt detected: {stripped[:100]}")
                    return PermissionRequest(
                        description=description,
                        matched_pattern=pattern.pattern,
                        matched_line=stripped,
                    )

        return None

    def has_patterns(self) -> bool:
        """Check if any valid patterns are configured."""
        return len(self._compiled) > 0
