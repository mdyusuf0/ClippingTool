"""Unit tests for clipfinder.captions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_words(n: int, start_offset: float = 0.0, duration: float = 30.0) -> list[dict[str, Any]]:
    step = duration / n
    return [
        {"text": f"word{i}", "start": start_offset + i * step, "end": start_offset + (i + 0.8) * step}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# build_srt_file
# ---------------------------------------------------------------------------

def test_build_srt_file_valid_format(tmp_path: Path) -> None:
    """build_srt_file should produce a file with the correct number of SRT blocks."""
    from clipfinder.captions import build_srt_file, group_words

    words = _make_words(10, duration=20.0)
    groups = group_words(words, max_per_group=5)

    srt_path = tmp_path / "test.srt"
    build_srt_file(groups, srt_path, mask_profanity=False)

    assert srt_path.exists()
    content = srt_path.read_text(encoding="utf-8")

    # Count sequence numbers: lines that are just integers
    seq_numbers = [ln.strip() for ln in content.splitlines() if ln.strip().isdigit()]
    assert len(seq_numbers) == len(groups), (
        f"Expected {len(groups)} SRT blocks, found {len(seq_numbers)}"
    )


def test_build_srt_file_has_arrows(tmp_path: Path) -> None:
    """Every SRT block must contain a ' --> ' timestamp line."""
    from clipfinder.captions import build_srt_file, group_words

    words = _make_words(6, duration=12.0)
    groups = group_words(words, max_per_group=3)

    srt_path = tmp_path / "arrows.srt"
    build_srt_file(groups, srt_path)

    content = srt_path.read_text(encoding="utf-8")
    arrow_lines = [ln for ln in content.splitlines() if " --> " in ln]
    assert len(arrow_lines) == len(groups)


def test_build_srt_file_timing_valid(tmp_path: Path) -> None:
    """All timestamps in the SRT file must be >= 00:00:00,000."""
    from clipfinder.captions import build_srt_file, group_words
    import re

    words = _make_words(8, duration=16.0)
    groups = group_words(words)
    srt_path = tmp_path / "timing.srt"
    build_srt_file(groups, srt_path)

    content = srt_path.read_text(encoding="utf-8")
    ts_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
    for match in ts_re.finditer(content):
        h, m, s, ms = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        total_ms = ((h * 3600 + m * 60 + s) * 1000) + ms
        assert total_ms >= 0, "Negative timestamp in SRT"


# ---------------------------------------------------------------------------
# build_ass_file
# ---------------------------------------------------------------------------

def test_build_ass_file_sections(tmp_path: Path) -> None:
    """ASS file must contain the three required section headers."""
    from clipfinder.captions import build_ass_file, group_words

    words = _make_words(5, duration=10.0)
    groups = group_words(words)
    ass_path = tmp_path / "test.ass"
    build_ass_file(groups, ass_path, style="bold", duration=10.0)

    assert ass_path.exists()
    content = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in content, "Missing [Script Info] section"
    assert "[V4+ Styles]" in content, "Missing [V4+ Styles] section"
    assert "[Events]" in content, "Missing [Events] section"


def test_build_ass_file_dialogue_count(tmp_path: Path) -> None:
    """Number of Dialogue lines must equal number of groups."""
    from clipfinder.captions import build_ass_file, group_words

    words = _make_words(12, duration=24.0)
    groups = group_words(words, max_per_group=4)
    ass_path = tmp_path / "dialogue_count.ass"
    build_ass_file(groups, ass_path, style="pop", duration=24.0)

    content = ass_path.read_text(encoding="utf-8")
    dialogue_lines = [ln for ln in content.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue_lines) == len(groups)


# ---------------------------------------------------------------------------
# Word grouping
# ---------------------------------------------------------------------------

def test_group_words_max_per_group() -> None:
    """12 words with max_per_group=5 should produce 3 groups: 5, 5, 2."""
    from clipfinder.captions import group_words

    words = _make_words(12, duration=24.0)
    groups = group_words(words, max_per_group=5)

    assert len(groups) == 3, f"Expected 3 groups, got {len(groups)}"
    assert len(groups[0]["words"]) == 5
    assert len(groups[1]["words"]) == 5
    assert len(groups[2]["words"]) == 2


def test_group_words_empty() -> None:
    """Empty word list should return an empty groups list."""
    from clipfinder.captions import group_words

    assert group_words([]) == []


def test_group_words_timing_preserved() -> None:
    """Group start/end should match the first/last word's timestamps."""
    from clipfinder.captions import group_words

    words = [
        {"text": "hello", "start": 1.0, "end": 1.5},
        {"text": "world", "start": 1.6, "end": 2.0},
    ]
    groups = group_words(words, max_per_group=5)
    assert len(groups) == 1
    assert groups[0]["start"] == pytest.approx(1.0)
    assert groups[0]["end"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Profanity masking
# ---------------------------------------------------------------------------

def test_profanity_masking_in_srt(tmp_path: Path) -> None:
    """Profane word 'fuck' in input should become '****' in SRT output."""
    from clipfinder.captions import build_srt_file, group_words

    words = [
        {"text": "fuck", "start": 0.0, "end": 0.5},
        {"text": "yeah", "start": 0.6, "end": 1.0},
    ]
    groups = group_words(words, max_per_group=5)
    srt_path = tmp_path / "profanity.srt"
    build_srt_file(groups, srt_path, mask_profanity=True)

    content = srt_path.read_text(encoding="utf-8")
    assert "fuck" not in content.lower(), "Profane word should be masked"
    assert "****" in content, "Expected asterisk masking"


def test_profanity_masking_in_ass(tmp_path: Path) -> None:
    """Profane word should be masked in ASS Dialogue lines too."""
    from clipfinder.captions import build_ass_file, group_words

    words = [{"text": "shit", "start": 0.0, "end": 0.4}]
    groups = group_words(words)
    ass_path = tmp_path / "profanity.ass"
    build_ass_file(groups, ass_path, mask_profanity=True)

    content = ass_path.read_text(encoding="utf-8")
    dialogue_lines = [ln for ln in content.splitlines() if ln.startswith("Dialogue:")]
    for line in dialogue_lines:
        assert "shit" not in line.lower()


# ---------------------------------------------------------------------------
# Non-Latin characters
# ---------------------------------------------------------------------------

def test_non_latin_arabic_in_srt(tmp_path: Path) -> None:
    """Arabic text must appear correctly (not mangled) in SRT output."""
    from clipfinder.captions import build_srt_file, group_words

    words = [{"text": "مرحبا", "start": 0.0, "end": 1.0}]
    groups = group_words(words)
    srt_path = tmp_path / "arabic.srt"
    build_srt_file(groups, srt_path)

    content = srt_path.read_text(encoding="utf-8")
    assert "مرحبا" in content, "Arabic text should be preserved in SRT"


def test_non_latin_arabic_in_ass(tmp_path: Path) -> None:
    """Arabic text must appear correctly in ASS output."""
    from clipfinder.captions import build_ass_file, group_words

    words = [{"text": "مرحبا", "start": 0.0, "end": 1.0}]
    groups = group_words(words)
    ass_path = tmp_path / "arabic.ass"
    build_ass_file(groups, ass_path)

    content = ass_path.read_text(encoding="utf-8")
    assert "مرحبا" in content, "Arabic text should be preserved in ASS"


# ---------------------------------------------------------------------------
# Timing: all timestamps >= 0 and <= clip duration
# ---------------------------------------------------------------------------

def test_all_timestamps_non_negative(tmp_path: Path) -> None:
    """All SRT group timestamps must be >= 0."""
    from clipfinder.captions import build_srt_file, group_words
    import re

    words = _make_words(8, start_offset=0.0, duration=20.0)
    groups = group_words(words)
    srt_path = tmp_path / "timestamps.srt"
    build_srt_file(groups, srt_path)

    content = srt_path.read_text(encoding="utf-8")
    ts_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
    for match in ts_re.finditer(content):
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        total_s = h * 3600 + m * 60 + s
        assert total_s >= 0


def test_all_timestamps_within_clip_duration() -> None:
    """Group end times must be <= clip duration."""
    from clipfinder.captions import group_words

    clip_duration = 15.0
    words = _make_words(6, start_offset=0.0, duration=clip_duration)
    groups = group_words(words)

    for grp in groups:
        assert grp["end"] <= clip_duration + 0.1, (
            f"Group end {grp['end']:.2f}s exceeds clip duration {clip_duration}s"
        )
