"""
Predefined agent configurations for supported AI CLI tools.

Each preset defines:
- binary: Default CLI executable name
- auto_args: Arguments with auto-approve flags (no permission prompts)
- interactive_args: Arguments without auto-approve (permission prompts enabled)
- permission_patterns: Regex patterns to detect permission prompts in stdout
- approval_response / denial_response: What to write to stdin on approve/deny
- env_exclude: Environment variable keys to exclude from subprocess env
"""

from dataclasses import dataclass, field


@dataclass
class AgentPreset:
    """Configuration preset for an AI CLI agent."""

    name: str
    binary: str
    auto_args: list[str] = field(default_factory=list)
    interactive_args: list[str] = field(default_factory=list)
    continue_args: list[str] = field(default_factory=list)
    continue_interactive_args: list[str] = field(default_factory=list)
    permission_patterns: list[str] = field(default_factory=list)
    approval_response: str = "y\n"
    denial_response: str = "n\n"
    env_exclude: list[str] = field(default_factory=list)

    def build_args(self, prompt: str, interactive: bool = False,
                   continue_mode: bool = False) -> list[str]:
        """Build CLI arguments for the given prompt.

        Args:
            prompt: The user prompt to pass to the CLI.
            interactive: If True, use interactive_args (permission prompts enabled).
            continue_mode: If True, use continue_args (resume previous conversation).

        Priority: continue_interactive > continue > interactive > auto
        """
        if continue_mode and interactive and self.continue_interactive_args:
            template = self.continue_interactive_args
        elif continue_mode and self.continue_args:
            template = self.continue_args
        elif interactive:
            template = self.interactive_args
        else:
            template = self.auto_args
        return [arg.replace("{prompt}", prompt) for arg in template]


# ── Preset Registry ──────────────────────────────────────────

PRESETS: dict[str, AgentPreset] = {
    "claude": AgentPreset(
        name="Claude Code",
        binary="claude",
        auto_args=["-p", "--dangerously-skip-permissions", "{prompt}"],
        interactive_args=["-p", "{prompt}"],
        continue_args=["-p", "--continue", "--dangerously-skip-permissions", "{prompt}"],
        continue_interactive_args=["-p", "--continue", "{prompt}"],
        permission_patterns=[
            r"(?i)allow\s+.+\?",
            r"(?i)do you want to (allow|continue|proceed|run)",
            r"\[Y/n\]",
            r"\[y/N\]",
            r"(?i)\(y(?:es)?/n(?:o)?\)",
            r"(?i)approve|deny|reject",
            r"(?i)permission.*(grant|allow|request)",
            r"(?i)want to execute",
            r"(?i)press enter to (allow|continue|approve)",
        ],
        approval_response="y\n",
        denial_response="n\n",
        env_exclude=["CLAUDECODE"],
    ),
    "gemini": AgentPreset(
        name="Gemini CLI",
        binary="gemini",
        auto_args=["-p", "{prompt}"],
        interactive_args=["-p", "{prompt}"],
        permission_patterns=[
            r"(?i)\(y(?:es)?/n(?:o)?\)",
            r"\[Y/n\]",
            r"\[y/N\]",
            r"(?i)do you want to (allow|continue|proceed|approve)",
            r"(?i)(allow|approve|permit|grant).*\?",
        ],
        approval_response="y\n",
        denial_response="n\n",
    ),
    "codex": AgentPreset(
        name="Codex CLI",
        binary="codex",
        auto_args=["--quiet", "--full-auto", "{prompt}"],
        interactive_args=["--quiet", "{prompt}"],
        permission_patterns=[
            r"(?i)\(y(?:es)?/n(?:o)?\)",
            r"\[Y/n\]",
            r"\[y/N\]",
            r"(?i)do you want to (allow|continue|proceed|approve)",
            r"(?i)(allow|approve|permit|grant).*\?",
            r"(?i)approve this action",
        ],
        approval_response="y\n",
        denial_response="n\n",
    ),
    "aider": AgentPreset(
        name="Aider",
        binary="aider",
        auto_args=["--message", "{prompt}", "--yes"],
        interactive_args=["--message", "{prompt}"],
        permission_patterns=[
            r"(?i)\(y(?:es)?/n(?:o)?\)",
            r"\[Y/n\]",
            r"\[y/N\]",
            r"(?i)allow .+ to",
            r"(?i)add .+ to the chat",
            r"(?i)create .+\?",
            r"(?i)edit .+\?",
        ],
        approval_response="y\n",
        denial_response="n\n",
    ),
}


def create_custom_preset(
    binary: str,
    args_template: list[str],
    permission_patterns: list[str] | None = None,
    approval_response: str = "y\n",
    denial_response: str = "n\n",
) -> AgentPreset:
    """Create a custom preset from user-defined configuration."""
    return AgentPreset(
        name=f"Custom ({binary})",
        binary=binary,
        auto_args=args_template,
        interactive_args=args_template,
        permission_patterns=permission_patterns or [
            r"(?i)\(y(?:es)?/n(?:o)?\)",
            r"\[Y/n\]",
            r"\[y/N\]",
            r"(?i)do you want to (allow|continue|proceed|approve)",
        ],
        approval_response=approval_response,
        denial_response=denial_response,
    )


def get_preset(agent_type: str) -> AgentPreset | None:
    """Get a preset by agent type name (case-insensitive)."""
    return PRESETS.get(agent_type.lower())


def get_supported_types() -> list[str]:
    """Get list of supported agent type names."""
    return list(PRESETS.keys())
