"""Unit tests for clipfinder.output."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from clipfinder.output import (
    create_zip,
    generate_local_metadata,
    try_gemini_enhance,
    write_clips_csv,
    write_summary_md,
)


def test_write_clips_csv(tmp_path: Path) -> None:
    """write_clips_csv writes all 10 required columns properly."""
    csv_path = tmp_path / "clips.csv"
    clips_data = [
        {
            "filename": "clip_01.mp4",
            "source_url_or_path": "https://example.com/video.mp4",
            "start": "0.00",
            "end": "15.00",
            "duration": "15.00",
            "score": "0.8500",
            "transcript_snippet": "This is an insane moment you have to see.",
            "suggested_title": "Insane moment you have to see",
            "suggested_description": "Watch this amazing moment.",
            "suggested_hashtags": "#viral #shorts",
        }
    ]

    write_clips_csv(clips_data, csv_path)
    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    expected_headers = [
        "filename",
        "source_url_or_path",
        "start",
        "end",
        "duration",
        "score",
        "transcript_snippet",
        "suggested_title",
        "suggested_description",
        "suggested_hashtags",
    ]
    for h in expected_headers:
        assert h in row, f"Missing header: {h}"
    assert row["filename"] == "clip_01.mp4"
    assert row["source_url_or_path"] == "https://example.com/video.mp4"
    assert row["duration"] == "15.00"


def test_write_summary_md(tmp_path: Path) -> None:
    """write_summary_md writes a formatted markdown document."""
    md_path = tmp_path / "summary.md"
    clips_data = [
        {
            "filename": "clip_01.mp4",
            "start": 0.0,
            "end": 15.0,
            "duration": 15.0,
            "score": 0.85,
            "suggested_title": "Epic Highlight",
            "suggested_description": "An epic highlight from the game.",
            "suggested_hashtags": "#gaming #shorts",
            "transcript_snippet": "Let's go clutch victory!",
        }
    ]

    write_summary_md(
        source_name="game_stream",
        source_url="https://youtube.com/watch?v=123",
        clips_data=clips_data,
        output_path=md_path,
        total_duration=120.0,
        processing_time=5.2,
    )

    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "# ClipFinder" in content
    assert "game_stream" in content
    assert "https://youtube.com/watch?v=123" in content
    assert "clip_01.mp4" in content
    assert "Epic Highlight" in content


def test_generate_local_metadata_presets() -> None:
    """generate_local_metadata handles different presets."""
    snippet = "Clutch play in the final circle victory royale!"
    hook_words = ["clutch", "insane"]

    # Gaming preset
    gaming_meta = generate_local_metadata(snippet, hook_words, score=0.9, preset="gaming")
    assert "suggested_title" in gaming_meta
    assert "suggested_description" in gaming_meta
    assert "suggested_hashtags" in gaming_meta
    assert "#gaming" in gaming_meta["suggested_hashtags"].lower()

    # Podcast preset
    podcast_meta = generate_local_metadata("The secret about human psychology", ["secret"], score=0.8, preset="podcast")
    assert "#podcast" in podcast_meta["suggested_hashtags"].lower()

    # General preset
    general_meta = generate_local_metadata(snippet, hook_words, score=0.7, preset="general")
    assert "#shorts" in general_meta["suggested_hashtags"].lower()


def test_try_gemini_enhance_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without GEMINI_API_KEY, try_gemini_enhance returns input unchanged."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sample_clips = [{"filename": "clip_01.mp4", "score": "0.9"}]
    enhanced = try_gemini_enhance(sample_clips, source_context="test")
    assert enhanced == sample_clips


def test_create_zip(tmp_path: Path) -> None:
    """create_zip creates a valid archive of the output directory files."""
    test_file = tmp_path / "clip_01.mp4"
    test_file.write_bytes(b"dummy video data")
    csv_file = tmp_path / "clips.csv"
    csv_file.write_text("header\nval", encoding="utf-8")

    zip_out = tmp_path / "archive.zip"
    res = create_zip(tmp_path, zip_out)
    assert res.exists()
    assert res.stat().st_size > 0
