"""Unit tests for clipfinder.preflight."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# run_preflight — ffmpeg / ffprobe missing
# ---------------------------------------------------------------------------

def test_preflight_fails_when_ffmpeg_missing() -> None:
    """run_preflight() must return False when ffmpeg is not on PATH."""
    from clipfinder.preflight import run_preflight

    with patch("shutil.which", return_value=None):
        result = run_preflight()

    assert result is False, "Expected False when ffmpeg/ffprobe not found"


def test_preflight_passes_when_ffmpeg_present(tmp_path) -> None:
    """run_preflight() should return True when ffmpeg + ffprobe are found and disk is OK."""
    from clipfinder.preflight import run_preflight
    import shutil

    # Simulate finding both tools
    def fake_which(name: str):
        if name in ("ffmpeg", "ffprobe"):
            return f"/usr/bin/{name}"
        return shutil.which(name)

    # Simulate plenty of disk space
    class FakeDiskUsage:
        free = 10 * 1024 ** 3  # 10 GB

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("shutil.disk_usage", return_value=FakeDiskUsage()),
    ):
        result = run_preflight()

    assert result is True, "Expected True when all tools present and disk space OK"


# ---------------------------------------------------------------------------
# Python version check
# ---------------------------------------------------------------------------

def test_preflight_fails_old_python() -> None:
    """run_preflight() must return False when running on Python < 3.9."""
    from clipfinder.preflight import run_preflight
    import shutil

    def fake_which(name: str):
        if name in ("ffmpeg", "ffprobe"):
            return f"/usr/bin/{name}"
        return shutil.which(name)

    # Monkeypatch sys.version_info
    old_version = sys.version_info
    fake_vi = type(sys.version_info)
    # Create a fake version_info tuple
    fake_version = (3, 8, 0, "final", 0)

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("sys.version_info", new=(3, 8, 0, "final", 0)),
    ):
        result = run_preflight()

    assert result is False, "Expected False for Python < 3.9"


def test_preflight_passes_current_python() -> None:
    """run_preflight() should not fail due to Python version on the current interpreter."""
    # Only meaningful if we're actually running 3.9+
    if sys.version_info < (3, 9):
        pytest.skip("Test environment is older than Python 3.9")

    from clipfinder.preflight import run_preflight
    import shutil

    def fake_which(name: str):
        if name in ("ffmpeg", "ffprobe"):
            return f"/usr/bin/{name}"
        return shutil.which(name)

    class FakeDiskUsage:
        free = 10 * 1024 ** 3

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("shutil.disk_usage", return_value=FakeDiskUsage()),
    ):
        result = run_preflight()

    assert result is True


# ---------------------------------------------------------------------------
# Disk space warning (soft failure — still returns True)
# ---------------------------------------------------------------------------

def test_preflight_low_disk_space_still_passes(capsys) -> None:
    """Low disk space should produce a warning but NOT make run_preflight return False."""
    from clipfinder.preflight import run_preflight
    import shutil

    def fake_which(name: str):
        if name in ("ffmpeg", "ffprobe"):
            return f"/usr/bin/{name}"
        return shutil.which(name)

    class LowDiskUsage:
        free = int(0.1 * 1024 ** 3)  # 100 MB — below threshold

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("shutil.disk_usage", return_value=LowDiskUsage()),
    ):
        result = run_preflight()

    # Should still return True; low disk is a warning not a hard failure
    assert result is True
