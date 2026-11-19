"""ClipFinder — captions: SRT and ASS subtitle generation."""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profanity masking
# ---------------------------------------------------------------------------

_PROFANITY_SET = frozenset(
    ["fuck", "fucking", "shit", "shitty", "ass", "asshole", "bitch", "bitchy",
     "crap", "damn", "hell", "cunt", "bastard", "piss", "cock", "dick"]
)


def mask_word(text: str) -> str:
    """Replace a profane word with asterisks of the same length."""
    if text.lower().rstrip("!?,. ") in _PROFANITY_SET:
        # Preserve trailing punctuation
        stripped = text.rstrip("!?,. ")
        trailing = text[len(stripped):]
        return "*" * len(stripped) + trailing
    return text


# ---------------------------------------------------------------------------
# Word grouping
# ---------------------------------------------------------------------------

def group_words(
    words: list[dict[str, Any]],
    max_per_group: int = 5,
) -> list[dict[str, Any]]:
    """
    Group sequential word dicts into subtitle blocks.

    Each block has:
    - ``start`` / ``end``: float seconds (relative to clip start)
    - ``text``: space-joined words in the group
    - ``words``: original word dicts

    Parameters
    ----------
    words:
        List of ``{"text": ..., "start": float, "end": float}`` dicts
        **already offset** to clip-relative time.
    max_per_group:
        Maximum words per subtitle block.
    """
    if not words:
        return []

    groups: list[dict[str, Any]] = []
    for i in range(0, len(words), max_per_group):
        chunk = words[i : i + max_per_group]
        start = chunk[0].get("start", 0.0)
        end = chunk[-1].get("end", start + 1.0)
        text = " ".join(w.get("text", "") for w in chunk).strip()
        groups.append({"start": start, "end": end, "text": text, "words": chunk})

    return groups


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------

def _srt_ts(seconds: float) -> str:
    """Format seconds as SRT timestamp: ``HH:MM:SS,mmm``."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_ts(seconds: float) -> str:
    """Format seconds as ASS timestamp: ``H:MM:SS.cc``."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ---------------------------------------------------------------------------
# SRT builder
# ---------------------------------------------------------------------------

def build_srt_file(
    groups: list[dict[str, Any]],
    out_path: Path,
    mask_profanity: bool = False,
) -> Path:
    """
    Write an SRT subtitle file from word groups.

    Parameters
    ----------
    groups:
        Output of :func:`group_words`.
    out_path:
        Destination ``.srt`` file path.
    mask_profanity:
        Replace profane words with asterisks.

    Returns the written path.
    """
    lines: list[str] = []
    for idx, grp in enumerate(groups, 1):
        text = grp["text"]
        if mask_profanity:
            text = " ".join(mask_word(w) for w in text.split())

        start_ts = _srt_ts(grp["start"])
        end_ts = _srt_ts(grp["end"])

        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.debug("Wrote SRT: %s (%d blocks)", out_path.name, len(groups))
    return out_path


# ---------------------------------------------------------------------------
# ASS builder
# ---------------------------------------------------------------------------

_ASS_STYLES: dict[str, dict[str, Any]] = {
    "bold": {
        "fontname": "Arial",
        "fontsize": 72,
        "primary": "&H00FFFFFF",
        "secondary": "&H0000FFFF",
        "outline": "&H00000000",
        "outline_width": 4,
        "bold": -1,
        "shadow": 2,
        "alignment": 2,  # bottom-centre
        "margin_v": 300,  # safe zone: >15% above bottom of 1920p (288px)
    },
    "pop": {
        "fontname": "Impact",
        "fontsize": 76,
        "primary": "&H00FFFFFF",
        "secondary": "&H0000FFFF",  # yellow active word highlight in karaoke
        "outline": "&H00000000",
        "outline_width": 4,
        "bold": -1,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 300,
    },
    "vice_city": {
        "fontname": "Impact",
        "fontsize": 78,
        "primary": "&H00FFFFFF",
        "secondary": "&H00D700FF",  # neon magenta / Vice City pink active word
        "outline": "&H00000000",
        "outline_width": 5,
        "bold": -1,
        "shadow": 3,
        "alignment": 2,
        "margin_v": 300,
    },
    "minimal": {
        "fontname": "Helvetica",
        "fontsize": 60,
        "primary": "&H00FFFFFF",
        "secondary": "&H0000FFFF",
        "outline": "&H80000000",
        "outline_width": 2,
        "bold": 0,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 300,
    },
}


def build_ass_file(
    groups: list[dict[str, Any]],
    out_path: Path,
    style: str = "bold",
    duration: float = 60.0,
    mask_profanity: bool = False,
    font_path: Path | None = None,
) -> Path:
    """
    Write an Advanced SubStation Alpha (ASS) subtitle file with word-by-word
    karaoke highlighting and safe-area margins.

    The file contains standard [Script Info], [V4+ Styles], and [Events]
    sections compatible with ffmpeg's ``ass`` filter.

    Parameters
    ----------
    groups:
        Output of :func:`group_words`.
    out_path:
        Destination ``.ass`` file path.
    style:
        One of ``bold``, ``pop``, ``minimal``.
    duration:
        Total clip duration in seconds (used for Script Info PlayResY).
    mask_profanity:
        Replace profane words with asterisks.
    font_path:
        Optional path to a custom font (e.g. Noto Sans).
    """
    s = _ASS_STYLES.get(style, _ASS_STYLES["bold"])
    font_name = font_path.stem if font_path and font_path.exists() else s["fontname"]

    script_info = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "Collisions: Normal\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "Timer: 100.0000\n"
        f"; Generated by ClipFinder (style={style})\n"
        "\n"
    )

    styles_section = (
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{s['fontsize']},{s['primary']},"
        f"{s.get('secondary', '&H0000FFFF')},{s['outline']},&H00000000,{s['bold']},0,0,0,"
        f"100,100,0,0,1,{s['outline_width']},{s['shadow']},"
        f"{s['alignment']},40,40,{s['margin_v']},1\n"
        "\n"
    )

    events_lines = [
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for grp in groups:
        words_in_grp = grp.get("words", [])
        if words_in_grp:
            # Word-by-word karaoke style using \k tags
            karaoke_tokens = []
            for w in words_in_grp:
                raw_w = w.get("text", "")
                if mask_profanity:
                    raw_w = mask_word(raw_w)
                w_start = w.get("start", grp["start"])
                w_end = w.get("end", grp["end"])
                dur_cs = max(1, int(round((w_end - w_start) * 100)))
                clean_w = raw_w.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                karaoke_tokens.append(f"{{\\k{dur_cs}}}{clean_w}")
            line_text = " ".join(karaoke_tokens)
        else:
            line_text = grp["text"]
            if mask_profanity:
                line_text = " ".join(mask_word(w) for w in line_text.split())
            line_text = line_text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

        line = (
            f"Dialogue: 0,{_ass_ts(grp['start'])},{_ass_ts(grp['end'])},"
            f"Default,,0,0,0,,{line_text}"
        )
        events_lines.append(line)

    content = script_info + styles_section + "\n".join(events_lines) + "\n"
    out_path.write_text(content, encoding="utf-8")
    logger.debug("Wrote ASS: %s (%d events)", out_path.name, len(groups))
    return out_path
