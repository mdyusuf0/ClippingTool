"""ClipFinder — preflight: system dependency and environment checks."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MIN_PYTHON = (3, 9)
_MIN_FREE_GB = 1.0  # warn threshold
_REQUIRED_TOOLS = ("ffmpeg", "ffprobe")


def run_preflight() -> bool:
    """
    Run all preflight checks.

    Returns True if the system satisfies all *hard* requirements, False
    otherwise.  Warnings are logged for soft requirements (e.g. disk space).
    """
    ok = True

    # Python version
    if sys.version_info < _MIN_PYTHON:
        logger.error(
            "Python %d.%d+ is required; found %s.",
            *_MIN_PYTHON,
            sys.version.split()[0],
        )
        ok = False
    else:
        logger.debug("Python version OK: %s", sys.version.split()[0])

    # Required external tools
    for tool in _REQUIRED_TOOLS:
        path = shutil.which(tool)
        if path is None:
            logger.error(
                "'%s' not found on PATH.\n"
                "  Windows : winget install ffmpeg\n"
                "  macOS   : brew install ffmpeg\n"
                "  Linux   : sudo apt install ffmpeg",
                tool,
            )
            ok = False
        else:
            logger.debug("'%s' found: %s", tool, path)

    # Disk space (soft warning only)
    try:
        stat = shutil.disk_usage(Path.cwd())
        free_gb = stat.free / (1024 ** 3)
        if free_gb < _MIN_FREE_GB:
            logger.warning(
                "Low disk space: %.1f GB free — rendering may fail.", free_gb
            )
        else:
            logger.debug("Disk space OK: %.1f GB free.", free_gb)
    except Exception as exc:
        logger.warning("Could not check disk space: %s", exc)

    return ok
