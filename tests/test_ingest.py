"""Unit tests for clipfinder.ingest."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# classify_input
# ---------------------------------------------------------------------------

def test_classify_youtube_url() -> None:
    from clipfinder.ingest import classify_input

    kind, resolved = classify_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert kind == "youtube"
    assert "youtube.com" in resolved


def test_classify_youtu_be_short() -> None:
    from clipfinder.ingest import classify_input

    kind, _ = classify_input("https://youtu.be/dQw4w9WgXcQ")
    assert kind == "youtube"


def test_classify_youtube_shorts() -> None:
    from clipfinder.ingest import classify_input

    kind, _ = classify_input("https://www.youtube.com/shorts/abcdef12345")
    assert kind == "youtube"


def test_classify_youtube_live() -> None:
    from clipfinder.ingest import classify_input

    kind, resolved = classify_input("https://www.youtube.com/live/liveStream123")
    assert kind == "youtube"
    assert "youtube.com" in resolved


def test_classify_kick_url() -> None:
    from clipfinder.ingest import classify_input

    kind, resolved = classify_input("https://kick.com/video/12345678-abcd-1234")
    assert kind == "kick"
    assert "kick.com" in resolved


def test_classify_gdrive_url() -> None:
    from clipfinder.ingest import classify_input

    kind, _ = classify_input("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view")
    assert kind == "gdrive"


def test_classify_direct_mp4_url() -> None:
    from clipfinder.ingest import classify_input

    kind, _ = classify_input("https://example.com/video.mp4")
    assert kind == "url"


def test_classify_local_file(tmp_path: Path) -> None:
    from clipfinder.ingest import classify_input

    video = tmp_path / "myvideo.mp4"
    video.write_bytes(b"dummy")
    kind, resolved = classify_input(str(video))
    assert kind == "file"
    assert Path(resolved).exists()


def test_classify_local_dir(tmp_path: Path) -> None:
    from clipfinder.ingest import classify_input

    kind, resolved = classify_input(str(tmp_path))
    assert kind == "dir"
    assert Path(resolved).is_dir()


def test_classify_nonexistent_file() -> None:
    from clipfinder.ingest import classify_input

    # Non-existent path that doesn't look like a URL → classified as 'file'
    kind, _ = classify_input("/nonexistent/path/video.mp4")
    assert kind == "file"


# ---------------------------------------------------------------------------
# sanitize_filename (from utils)
# ---------------------------------------------------------------------------

def test_sanitize_filename_basic() -> None:
    from clipfinder.utils import sanitize_filename

    result = sanitize_filename("My Great Video 2024")
    assert " " not in result
    assert result == "My_Great_Video_2024"


def test_sanitize_filename_emoji_removal() -> None:
    from clipfinder.utils import sanitize_filename

    result = sanitize_filename("Cool Video 🎬 Highlights")
    assert "🎬" not in result
    # Should still produce something useful
    assert len(result) > 0
    assert result != "untitled"


def test_sanitize_filename_unicode_normalization() -> None:
    from clipfinder.utils import sanitize_filename

    # Accented characters should be normalised / stripped
    result = sanitize_filename("Vídeo de Crédito")
    assert isinstance(result, str)
    assert len(result) > 0


def test_sanitize_filename_length_truncation() -> None:
    from clipfinder.utils import sanitize_filename

    long_name = "A" * 200
    result = sanitize_filename(long_name, max_len=80)
    assert len(result) <= 80


def test_sanitize_filename_spaces_to_underscores() -> None:
    from clipfinder.utils import sanitize_filename

    result = sanitize_filename("hello world foo bar")
    assert " " not in result
    assert "_" in result


def test_sanitize_filename_empty_fallback() -> None:
    from clipfinder.utils import sanitize_filename

    result = sanitize_filename("🎬🎥🎞️")  # all emoji, stripped to nothing
    assert result == "untitled"


# ---------------------------------------------------------------------------
# permission_gate
# ---------------------------------------------------------------------------

def test_permission_gate_flag_true() -> None:
    """When has_permission_flag=True, gate should return True regardless of URLs."""
    from main import permission_gate

    sources = [{"raw": "https://www.youtube.com/watch?v=abc", "kind": "youtube", "resolved": "https://www.youtube.com/watch?v=abc"}]
    result = permission_gate(sources, has_permission_flag=True, interactive=False)
    assert result is True


def test_permission_gate_no_flag_non_interactive() -> None:
    """When no flag and not interactive, should return False for URL sources."""
    from main import permission_gate

    sources = [{"raw": "https://www.youtube.com/watch?v=abc", "kind": "youtube", "resolved": ""}]
    result = permission_gate(sources, has_permission_flag=False, interactive=False)
    assert result is False


def test_permission_gate_local_files_always_ok() -> None:
    """Local file sources never trigger the permission gate."""
    from main import permission_gate

    sources = [{"raw": "/path/to/video.mp4", "kind": "file", "resolved": "/path/to/video.mp4"}]
    result = permission_gate(sources, has_permission_flag=False, interactive=False)
    assert result is True


def test_permission_gate_interactive_no(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulating user typing 'n' at the prompt should return False."""
    from main import permission_gate

    monkeypatch.setattr("builtins.input", lambda _: "n")
    sources = [{"raw": "https://www.youtube.com/watch?v=abc", "kind": "youtube", "resolved": ""}]
    result = permission_gate(sources, has_permission_flag=False, interactive=True)
    assert result is False


def test_permission_gate_interactive_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulating user typing 'y' should return True."""
    from main import permission_gate

    monkeypatch.setattr("builtins.input", lambda _: "y")
    # Console is imported inside the function, patch via rich.console
    with patch("rich.console.Console") as mock_console:
        mock_console.return_value = MagicMock()
        from main import permission_gate as pg

        sources = [{"raw": "https://www.youtube.com/watch?v=abc", "kind": "youtube", "resolved": ""}]
        result = pg(sources, has_permission_flag=False, interactive=True)
    assert result is True


# ---------------------------------------------------------------------------
# collect_inputs — directory expansion
# ---------------------------------------------------------------------------

def test_collect_inputs_from_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """collect_inputs with a directory should detect .mp4 files."""
    # Create dummy video files
    for name in ("a.mp4", "b.mp4", "notes.txt"):
        (tmp_path / name).write_bytes(b"dummy")

    # Mock yt-dlp to prevent any network calls
    mock_yt_dlp = MagicMock()
    sys.modules.setdefault("yt_dlp", mock_yt_dlp)

    from main import collect_inputs

    sources = collect_inputs(
        positional=[str(tmp_path)],
        links_file=None,
        max_source_hours=None,
        playlist_items=None,
    )

    assert len(sources) == 1
    assert sources[0]["kind"] == "dir"


def test_collect_inputs_links_file(tmp_path: Path) -> None:
    """Links file should add extra sources."""
    links = tmp_path / "links.txt"
    links.write_text("https://www.youtube.com/watch?v=abc\n# comment\n\n", encoding="utf-8")

    video = tmp_path / "local.mp4"
    video.write_bytes(b"dummy")

    from main import collect_inputs

    sources = collect_inputs(
        positional=[str(video)],
        links_file=str(links),
        max_source_hours=None,
        playlist_items=None,
    )

    kinds = [s["kind"] for s in sources]
    assert "file" in kinds
    assert "youtube" in kinds


def test_download_source_live_stream_options(tmp_path: Path) -> None:
    """Verify live stream download configures external ffmpeg downloader and duration."""
    from clipfinder.ingest import download_source
    import yt_dlp

    captured_opts = {}

    class DummyYDL:
        def __init__(self, opts):
            nonlocal captured_opts
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download=True):
            if not download:
                return {"is_live": True, "live_status": "is_live", "title": "GTA 6 Live"}
            out_file = tmp_path / "live_clip.mp4"
            out_file.write_bytes(b"dummy_stream_bytes")
            return {"title": "live_clip"}

        def prepare_filename(self, info):
            return str(tmp_path / "live_clip.mp4")

    with patch("yt_dlp.YoutubeDL", side_effect=DummyYDL):
        result = download_source(
            "https://www.youtube.com/live/gta6stream",
            tmp_path,
            config={"live_duration": 5.0, "live_from_start": True},
        )
        assert result is not None
        assert result.exists()
        assert captured_opts.get("external_downloader") == "ffmpeg"
        assert captured_opts.get("live_from_start") is True
        assert captured_opts.get("external_downloader_args") == {"ffmpeg": ["-t", "300"]}

