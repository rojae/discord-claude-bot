import asyncio
import logging
import os
import time
import uuid
from src.agent.session import Session, SessionManager, SessionStatus
from src.agent.permission import PermissionDetector
from src.config import settings

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runs AI CLI agents asynchronously and manages sessions."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._semaphore = asyncio.Semaphore(settings.agent_max_concurrent)
        self._tasks: set[asyncio.Task] = set()  # Keep task references to prevent GC
        self._preset = settings.get_agent_preset()
        self._interactive = settings.is_permission_relay or settings.is_permission_deny
        logger.info(
            f"Agent preset: {self._preset.name} (binary={self._preset.binary}) "
            f"permission_mode={settings.agent_permission_mode}"
        )

    async def run(self, prompt: str, user_id: int, channel_id: int,
                  permission_handler=None, continue_mode: bool = False) -> Session:
        """Start a new agent task.

        Args:
            prompt: The user prompt to send to the agent.
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            permission_handler: Optional handler with async request_permission(description) -> bool.
                                Used when agent_permission_mode is 'relay'.
            continue_mode: If True, resume previous conversation using --continue flag.
        """
        session_id = str(uuid.uuid4())[:8]
        session = await self.session_manager.create(session_id, prompt, user_id, channel_id)
        logger.info(f"[{session_id}] Task registered | user={user_id} | continue={continue_mode} | prompt={prompt[:80]!r}")

        task = asyncio.create_task(self._execute(session, permission_handler, continue_mode))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)  # Auto-remove on completion
        return session

    async def _execute(self, session: Session, permission_handler=None,
                       continue_mode: bool = False) -> None:
        async with self._semaphore:
            session.status = SessionStatus.RUNNING
            logger.info(f"[{session.session_id}] Execution started (continue={continue_mode})")
            try:
                # Build environment, excluding preset-specific keys
                env = {
                    k: v for k, v in os.environ.items()
                    if k not in self._preset.env_exclude
                }

                # Build command based on permission mode and continue mode
                cmd_args = self._preset.build_args(
                    session.prompt,
                    interactive=self._interactive,
                    continue_mode=continue_mode,
                )
                cmd = [self._preset.binary] + cmd_args
                logger.debug(f"[{session.session_id}] Command: {cmd}")

                # Enable stdin PIPE only for interactive modes (relay/deny)
                stdin_mode = asyncio.subprocess.PIPE if self._interactive else None

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=stdin_mode,
                    cwd=settings.agent_working_dir,
                    env=env,
                )
                session.process = process

                # Collect stderr concurrently to prevent buffer deadlock
                stderr_lines: list[bytes] = []

                async def _drain_stderr():
                    async for raw in process.stderr:
                        stderr_lines.append(raw)

                stderr_task = asyncio.create_task(_drain_stderr())

                try:
                    if self._interactive:
                        lines = await self._read_with_permissions(
                            process, session, permission_handler
                        )
                    else:
                        lines = await self._read_stdout(process, session)

                    await process.wait()
                    await stderr_task  # Ensure stderr is fully drained

                    stderr_data = b"".join(stderr_lines).decode().strip()
                    if process.returncode != 0:
                        error_msg = stderr_data or f"exit code {process.returncode}"
                        logger.warning(f"[{session.session_id}] Non-zero exit: {error_msg}")
                        session.fail(error_msg)
                    else:
                        output = "".join(lines).strip()
                        logger.info(f"[{session.session_id}] Completed ({session.elapsed})")
                        session.finish(output)

                except asyncio.TimeoutError:
                    process.terminate()
                    stderr_task.cancel()
                    await process.wait()
                    msg = f"Timeout: exceeded {settings.agent_timeout}s"
                    logger.warning(f"[{session.session_id}] {msg}")
                    session.fail(msg)

            except FileNotFoundError:
                msg = f"`{self._preset.binary}` not found. Please verify {self._preset.name} CLI is installed."
                logger.error(f"[{session.session_id}] {msg}")
                session.fail(msg)
            except Exception as e:
                logger.exception(f"[{session.session_id}] Exception occurred")
                session.fail(str(e))
            finally:
                logger.debug(f"[{session.session_id}] _execute finished, status={session.status}")

    async def _read_stdout(self, process, session: Session) -> list[str]:
        """Read stdout until EOF with overall timeout (auto_approve mode)."""
        lines = []

        async def _reader():
            async for raw in process.stdout:
                line = raw.decode()
                lines.append(line)
                session.progress = "".join(lines[-50:]).strip()

        await asyncio.wait_for(_reader(), timeout=float(settings.agent_timeout))
        return lines

    async def _read_with_permissions(self, process, session: Session,
                                     permission_handler=None) -> list[str]:
        """Read stdout with permission detection and relay (relay/deny mode).

        Uses stall detection: when no output for stall_timeout seconds,
        checks the output buffer for permission patterns. If found,
        relays to Discord (relay mode) or auto-denies (deny mode).
        """
        lines = []
        buffer = []
        detector = PermissionDetector(self._preset.permission_patterns)
        start_time = time.monotonic()
        overall_timeout = float(settings.agent_timeout)
        stall_timeout = settings.agent_stall_timeout

        while True:
            # Check overall timeout
            elapsed = time.monotonic() - start_time
            remaining = overall_timeout - elapsed
            if remaining <= 0:
                raise asyncio.TimeoutError()

            try:
                raw = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=min(stall_timeout, remaining),
                )

                if not raw:  # EOF
                    break

                line = raw.decode()
                lines.append(line)
                buffer.append(line)
                session.progress = "".join(lines[-50:]).strip()

            except asyncio.TimeoutError:
                # Check if it's the overall timeout
                if time.monotonic() - start_time >= overall_timeout:
                    raise

                # Output stalled — check if process is still running
                if process.returncode is not None:
                    break  # Process exited

                # Check buffer for permission prompt
                request = detector.detect(buffer)
                if request:
                    # Process may have exited while we were checking
                    if process.returncode is not None:
                        logger.info(f"[{session.session_id}] Process exited before permission response")
                        break

                    approved = await self._handle_permission(
                        process, session, request, permission_handler
                    )
                    action = "approved" if approved else "denied"
                    logger.info(f"[{session.session_id}] Permission {action}: {request.matched_line[:80]}")
                    buffer.clear()

                    # Process may have exited during permission wait
                    if process.returncode is not None:
                        break
                # else: just a slow computation, keep waiting

        return lines

    async def _handle_permission(self, process, session: Session,
                                 request, permission_handler) -> bool:
        """Handle a detected permission prompt.

        - relay mode: send to Discord via permission_handler
        - deny mode: auto-deny without asking
        """
        if settings.is_permission_deny:
            # Auto-deny mode
            approved = False
        elif permission_handler:
            # Relay mode — ask user via Discord
            approved = await permission_handler.request_permission(request.description)
        else:
            # No handler available — auto-approve as fallback
            logger.warning(f"[{session.session_id}] No permission handler, auto-approving")
            approved = True

        # Write response to stdin (process may have exited during user decision)
        if process.returncode is not None:
            logger.warning(f"[{session.session_id}] Process exited before stdin write, skipping")
            return approved

        response = self._preset.approval_response if approved else self._preset.denial_response
        try:
            process.stdin.write(response.encode())
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError):
            logger.warning(f"[{session.session_id}] Failed to write to stdin (process may have exited)")

        return approved
