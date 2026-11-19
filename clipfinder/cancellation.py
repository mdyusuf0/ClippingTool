"""ClipFinder — cancellation: cooperative cancellation and process termination."""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Any

logger = logging.getLogger(__name__)


class CancellationError(Exception):
    """Raised when an active processing task is canceled by the user."""
    pass


class CancellationManager:
    """
    Thread-safe manager for cooperative cancellation and subprocess tracking.
    Allows immediate termination of ffmpeg, yt-dlp, and Whisper tasks.
    """

    def __init__(self) -> None:
        self._canceled: bool = False
        self._lock = threading.Lock()
        self._active_processes: set[subprocess.Popen[Any]] = set()

    def reset(self) -> None:
        """Reset the cancellation token for a fresh run."""
        with self._lock:
            self._canceled = False
            self._active_processes.clear()

    def cancel(self) -> None:
        """
        Request cancellation: set flag and kill all registered running subprocesses.
        """
        with self._lock:
            self._canceled = True
            logger.info("Cancellation requested. Terminating %d active processes.", len(self._active_processes))
            for proc in list(self._active_processes):
                try:
                    proc.kill()
                    logger.debug("Terminated subprocess PID %s", getattr(proc, "pid", None))
                except Exception as exc:
                    logger.debug("Could not terminate subprocess: %s", exc)
            self._active_processes.clear()

    def is_canceled(self) -> bool:
        """Return True if cancellation was requested."""
        with self._lock:
            return self._canceled

    def check_canceled(self) -> None:
        """Raise CancellationError if cancellation was requested."""
        if self.is_canceled():
            raise CancellationError("Operation was canceled by user.")

    def register_process(self, proc: subprocess.Popen[Any]) -> None:
        """Register a subprocess for termination if cancel() is invoked."""
        with self._lock:
            if self._canceled:
                try:
                    proc.kill()
                except Exception:
                    pass
                return
            self._active_processes.add(proc)

    def unregister_process(self, proc: subprocess.Popen[Any]) -> None:
        """Unregister a completed subprocess."""
        with self._lock:
            self._active_processes.discard(proc)

    def run_command(
        self,
        cmd: list[str],
        capture_output: bool = True,
        text: bool = False,
        check: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[Any]:
        """
        Execute a subprocess command while tracking it for instant cancellation.
        """
        self.check_canceled()

        stdout_pipe = subprocess.PIPE if capture_output else None
        stderr_pipe = subprocess.PIPE if capture_output else None

        proc = subprocess.Popen(
            cmd,
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            text=text,
            **kwargs,
        )
        self.register_process(proc)

        try:
            out, err = proc.communicate()
            if self.is_canceled():
                raise CancellationError("Process canceled by user.")

            retcode = proc.poll()
            if check and retcode != 0:
                raise subprocess.CalledProcessError(retcode or 1, cmd, output=out, stderr=err)

            return subprocess.CompletedProcess(cmd, retcode or 0, out, err)
        except Exception:
            if self.is_canceled():
                raise CancellationError("Process canceled by user.")
            raise
        finally:
            self.unregister_process(proc)


# Global singleton instance
cancellation_token = CancellationManager()
