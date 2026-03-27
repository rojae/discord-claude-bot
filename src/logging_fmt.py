"""
Colorful terminal logging formatter with ANSI escape codes.

Provides:
- Color-coded log levels with icons
- Dim timestamps
- Bold module names (shortened)
- Clean, modern terminal output
"""

import logging
import sys

# ── ANSI Escape Codes ────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

# Foreground colors
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Bright foreground
BRIGHT_BLACK = "\033[90m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

# Background colors
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"

# ── Level Styles ─────────────────────────────────────────────

LEVEL_STYLES = {
    logging.DEBUG: {
        "icon": "·",
        "label": "DBG",
        "color": BRIGHT_BLACK,
    },
    logging.INFO: {
        "icon": "›",
        "label": "INF",
        "color": CYAN,
    },
    logging.WARNING: {
        "icon": "▲",
        "label": "WRN",
        "color": YELLOW,
    },
    logging.ERROR: {
        "icon": "✖",
        "label": "ERR",
        "color": RED,
    },
    logging.CRITICAL: {
        "icon": "◆",
        "label": "CRT",
        "color": f"{BOLD}{BG_RED}{WHITE}",
    },
}

# Module name abbreviations for cleaner output
_MODULE_MAP = {
    "__main__": "main",
    "src.bot.client": "bot",
    "src.agent.runner": "runner",
    "src.agent.session": "session",
    "src.agent.output_parser": "parser",
    "src.agent.permission": "perm",
    "src.commands.task": "task",
    "src.commands.registry": "registry",
    "src.commands.status_cancel": "cmd",
    "src.security.guard": "guard",
    "src.config": "config",
    "src.bot.views": "views",
}


def _shorten_module(name: str) -> str:
    """Shorten module name for display."""
    if name in _MODULE_MAP:
        return _MODULE_MAP[name]
    # Strip common prefixes
    for prefix in ("src.", "discord."):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _supports_color() -> bool:
    """Check if the terminal supports color output."""
    if not hasattr(sys.stderr, "isatty"):
        return False
    if not sys.stderr.isatty():
        return False
    return True


class ColorFormatter(logging.Formatter):
    """Modern colorful log formatter for terminal output."""

    def __init__(self):
        super().__init__()
        self._use_color = _supports_color()

    def format(self, record: logging.LogRecord) -> str:
        style = LEVEL_STYLES.get(record.levelno, LEVEL_STYLES[logging.INFO])
        module = _shorten_module(record.name)
        message = record.getMessage()

        if self._use_color:
            return self._format_color(record, style, module, message)
        return self._format_plain(record, style, module, message)

    def _format_color(self, record, style, module, message) -> str:
        icon = style["icon"]
        color = style["color"]
        label = style["label"]

        # Dim timestamp
        ts = self.formatTime(record, "%H:%M:%S")
        time_str = f"{DIM}{ts}{RESET}"

        # Colored level badge
        level_str = f"{color}{BOLD}{icon} {label}{RESET}"

        # Bold cyan module name
        mod_str = f"{BRIGHT_BLUE}{module}{RESET}"

        # Message color: dim for debug, normal for info, colored for warn/error
        if record.levelno <= logging.DEBUG:
            msg_str = f"{DIM}{message}{RESET}"
        elif record.levelno >= logging.WARNING:
            msg_str = f"{color}{message}{RESET}"
        else:
            msg_str = message

        line = f"  {time_str} {level_str} {mod_str} {DIM}│{RESET} {msg_str}"

        # Append exception info if present
        if record.exc_info and record.exc_info[1]:
            exc_text = self.formatException(record.exc_info)
            line += f"\n{RED}{exc_text}{RESET}"

        return line

    def _format_plain(self, record, style, module, message) -> str:
        ts = self.formatTime(record, "%H:%M:%S")
        label = style["label"]
        line = f"  {ts} {label} {module} | {message}"
        if record.exc_info and record.exc_info[1]:
            line += f"\n{self.formatException(record.exc_info)}"
        return line


# ── Startup Banner ───────────────────────────────────────────

BANNER = f"""{BRIGHT_CYAN}{BOLD}
  ╔══════════════════════════════════════════════╗
  ║                                              ║
  ║   🤖  discord-claude-bot                     ║
  ║                                              ║
  ╚══════════════════════════════════════════════╝{RESET}
"""

BANNER_PLAIN = """
  +----------------------------------------------+
  |   discord-claude-bot                         |
  +----------------------------------------------+
"""


def print_banner():
    """Print the startup banner."""
    if _supports_color():
        print(BANNER, file=sys.stderr)
    else:
        print(BANNER_PLAIN, file=sys.stderr)


def print_config_table(rows: list[tuple[str, str]]):
    """Print a nicely formatted configuration table."""
    use_color = _supports_color()

    if use_color:
        header = f"  {BRIGHT_MAGENTA}{BOLD}Configuration{RESET}"
        divider = f"  {DIM}{'─' * 44}{RESET}"
        print(header, file=sys.stderr)
        print(divider, file=sys.stderr)
        for label, value in rows:
            lbl = f"{DIM}{label:<22}{RESET}"
            val = f"{BRIGHT_GREEN}{value}{RESET}"
            print(f"  {lbl} {val}", file=sys.stderr)
        print(divider, file=sys.stderr)
    else:
        print("  Configuration", file=sys.stderr)
        print(f"  {'─' * 44}", file=sys.stderr)
        for label, value in rows:
            print(f"  {label:<22} {value}", file=sys.stderr)
        print(f"  {'─' * 44}", file=sys.stderr)
    print(file=sys.stderr)
