"""Tests for clipfinder.render."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

skip_no_ffmpeg = pytest.mark.skipif(
    not FFMPEG_AVAILABLE, reason="ffmpeg not available on PATH"
)


# ---------------------------------------------------------------------------
# render_clip — blur style on a normal landscape video
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_blur_produces_file(normal_video: Path, tmp_path: Path) -> None:
    """render_clip with style='blur' should create a non-empty .mp4 file."""
    from clipfinder.render import render_clip

    out = tmp_path / "blur_clip.mp4"
    ok = render_clip(
        source=normal_video,
        start=5.0,
        end=20.0,
        out_path=out,
        style="blur",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )

    assert ok is True, "render_clip should return True on success"
    assert out.exists(), "Output file should exist"
    assert out.stat().st_size > 0, "Output file should not be empty"


@skip_no_ffmpeg
def test_render_clip_output_duration_approx(normal_video: Path, tmp_path: Path) -> None:
    """
    Rendered clip duration should be approximately equal to (end - start).
    We allow ±2 s tolerance for ffmpeg seek inaccuracy.
    """
    import subprocess, json

    from clipfinder.render import render_clip

    out = tmp_path / "dur_check.mp4"
    render_clip(
        source=normal_video,
        start=0.0,
        end=15.0,
        out_path=out,
        style="crop",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(out)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    assert abs(duration - 15.0) < 2.0, f"Unexpected duration: {duration:.2f}s"


# ---------------------------------------------------------------------------
# render_clip — no audio video
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_no_audio_handles_gracefully(no_audio_video: Path, tmp_path: Path) -> None:
    """
    render_clip on a video with no audio stream should either succeed
    (producing a video-only clip) or fail cleanly (return False), not crash.
    """
    from clipfinder.render import render_clip

    out = tmp_path / "no_audio_clip.mp4"
    result = render_clip(
        source=no_audio_video,
        start=0.0,
        end=20.0,
        out_path=out,
        style="blur",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )
    # Must not raise; result is True or False
    assert isinstance(result, bool)
    if result:
        assert out.exists()
        assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# render_clip — portrait video with crop
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_portrait_crop(portrait_video: Path, tmp_path: Path) -> None:
    """Portrait video with style='crop' should produce a valid .mp4."""
    from clipfinder.render import render_clip

    out = tmp_path / "portrait_crop.mp4"
    ok = render_clip(
        source=portrait_video,
        start=5.0,
        end=20.0,
        out_path=out,
        style="crop",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )
    assert ok is True
    assert out.exists()
    assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# render_clip — ASS burn-in
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_ass_burnin(normal_video: Path, tmp_path: Path) -> None:
    """Providing a valid .ass file should not cause render_clip to fail."""
    from clipfinder.render import render_clip
    from clipfinder.captions import build_ass_file, group_words

    # Build a minimal ASS file
    words = [
        {"text": "Hello", "start": 0.0, "end": 1.0},
        {"text": "World", "start": 1.1, "end": 2.0},
    ]
    groups = group_words(words)
    ass_path = tmp_path / "sub.ass"
    build_ass_file(groups, ass_path, style="bold", duration=15.0)

    out = tmp_path / "ass_burnin.mp4"
    ok = render_clip(
        source=normal_video,
        start=0.0,
        end=15.0,
        out_path=out,
        style="crop",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
        ass_path=ass_path,
    )
    assert ok is True
    assert out.exists()
    assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# render_clip — invalid time range
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_invalid_range_returns_false(normal_video: Path, tmp_path: Path) -> None:
    """render_clip with end <= start should return False without crashing."""
    from clipfinder.render import render_clip

    out = tmp_path / "invalid.mp4"
    result = render_clip(
        source=normal_video,
        start=30.0,
        end=10.0,  # end < start
        out_path=out,
        style="blur",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )
    assert result is False


# ---------------------------------------------------------------------------
# render_clip — corrupt source
# ---------------------------------------------------------------------------

@skip_no_ffmpeg
def test_render_clip_corrupt_source_returns_false(corrupt_video: Path, tmp_path: Path) -> None:
    """render_clip on a corrupt file should return False, not raise."""
    from clipfinder.render import render_clip

    out = tmp_path / "from_corrupt.mp4"
    result = render_clip(
        source=corrupt_video,
        start=0.0,
        end=10.0,
        out_path=out,
        style="blur",
        crf=28,
        preset="ultrafast",
        audio_bitrate="96k",
    )
    assert result is False
