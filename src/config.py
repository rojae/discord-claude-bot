import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List

from src.agent.presets import get_preset, create_custom_preset, get_supported_types

logger = logging.getLogger(__name__)

_VALID_PERMISSION_MODES = frozenset({"auto_approve", "relay", "deny"})
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── Discord ───────────────────────────────────────────────
    discord_token: str
    command_prefix: str = "/"                        # Command prefix
    allowed_channel_ids: List[int] = Field(default_factory=list)
    allowed_user_ids: List[int] = Field(default_factory=list)
    admin_user_ids: List[int] = Field(default_factory=list)   # Admin users (manage bans & allowed users)
    discord_message_limit: int = 2000                # Discord message character limit
    discord_webhook_url: str = ""                     # Webhook URL for start/stop notifications

    # ── Agent ─────────────────────────────────────────────────
    agent_type: str = "claude"                       # claude | gemini | codex | aider | custom
    agent_binary: str = ""                           # CLI executable path (auto-detected from preset if empty)
    agent_args: str = ""                             # Custom args template (comma-separated, use {prompt} placeholder)
    agent_working_dir: str = "."                     # Agent working directory
    agent_timeout: int = 300                         # Task timeout (seconds)
    agent_max_output: int = 3000                     # Max output characters for Discord
    agent_max_concurrent: int = 3                    # Max concurrent sessions
    agent_max_per_user: int = 10                      # Max concurrent tasks per user
    session_ttl_seconds: int = 1800                    # How long to keep completed sessions (for follow-ups)

    # ── Permission ────────────────────────────────────────────
    agent_permission_mode: str = "auto_approve"      # auto_approve | relay | deny
    agent_permission_timeout: float = 300.0          # Seconds to wait for user response
    agent_stall_timeout: float = 5.0                 # Seconds of no output before checking for permission prompt

    # ── Polling ───────────────────────────────────────────────
    poll_interval_seconds: float = 1.0               # Task completion polling interval

    # ── Notifications ─────────────────────────────────────────
    notify_on_complete: bool = True
    notify_on_error: bool = True

    # ── Restart ───────────────────────────────────────────────
    skip_missed_messages: bool = True                 # Skip queued messages on restart

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"                          # DEBUG | INFO | WARNING | ERROR

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        v = v.lower()
        valid = get_supported_types() + ["custom"]
        if v not in valid:
            raise ValueError(f"agent_type must be one of {valid}, got '{v}'")
        return v

    @field_validator("agent_permission_mode")
    @classmethod
    def validate_permission_mode(cls, v: str) -> str:
        v = v.lower()
        if v not in _VALID_PERMISSION_MODES:
            raise ValueError(f"agent_permission_mode must be one of {sorted(_VALID_PERMISSION_MODES)}, got '{v}'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in _VALID_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got '{v}'")
        return v

    @field_validator("agent_timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 10:
            raise ValueError(f"agent_timeout must be >= 10 seconds, got {v}")
        return v

    @field_validator("agent_max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"agent_max_concurrent must be >= 1, got {v}")
        return v

    def get_agent_preset(self):
        """Resolve the agent preset from configuration."""
        preset = get_preset(self.agent_type)

        if preset is None and self.agent_type != "custom":
            logger.warning(
                f"Unknown agent type '{self.agent_type}'. "
                f"Supported: {get_supported_types() + ['custom']}. Falling back to 'claude'."
            )
            preset = get_preset("claude")

        # Custom type or override binary/args
        if self.agent_type == "custom" or (self.agent_binary and self.agent_args):
            binary = self.agent_binary or (preset.binary if preset else "claude")
            args_template = [a.strip() for a in self.agent_args.split(",") if a.strip()]
            if not args_template:
                args_template = ["{prompt}"]
            return create_custom_preset(binary=binary, args_template=args_template)

        # Override just the binary path (keep preset args)
        if self.agent_binary and preset:
            from dataclasses import replace
            return replace(preset, binary=self.agent_binary)

        return preset

    @property
    def is_permission_relay(self) -> bool:
        return self.agent_permission_mode == "relay"

    @property
    def is_permission_deny(self) -> bool:
        return self.agent_permission_mode == "deny"


settings = Settings()
