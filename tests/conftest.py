"""Shared pytest fixtures for ClipFinder tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


@pytest.fixture(scope="session")
def tmp_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped temporary directory for test artifacts."""
    return tmp_path_factory.mktemp("clipfinder_tests")


@pytest.fixture(scope="session")
def normal_video(tmp_dir: Path) -> Path:
    """
    2-minute 1920×1080 test video with a 440 Hz sine tone.

    Uses ffmpeg lavfi sources — no real media files required.
    Skipped if ffmpeg is not available.
    """
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg not available")

    path = tmp_dir / "test_normal.mp4"
    if path.exists():
        return path  # already created by a previous test run in this session

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=120:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=120",
        "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def no_audio_video(tmp_dir: Path) -> Path:
    """30-second 1280×720 video with no audio stream."""
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg not available")

    path = tmp_dir / "test_no_audio.mp4"
    if path.exists():
        return path

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=30:size=1280x720:rate=30",
        "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
        "-an",  # no audio
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def portrait_video(tmp_dir: Path) -> Path:
    """60-second portrait (1080×1920) video with a 220 Hz sine tone."""
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg not available")

    path = tmp_dir / "test_portrait.mp4"
    if path.exists():
        return path

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=60:size=1080x1920:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=60",
        "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def corrupt_video(tmp_dir: Path) -> Path:
    """A file that is NOT a valid video — just random bytes."""
    path = tmp_dir / "corrupt.mp4"
    if not path.exists():
        path.write_bytes(b"this is not a video file" * 100)
    return path
