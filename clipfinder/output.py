"""
clipfinder/output.py
====================
Write CSV reports, Markdown summaries, generate local metadata (titles,
descriptions, hashtags), optionally enhance with Gemini, and create zip archives.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

#: Ordered column names for the output CSV.
_CSV_FIELDNAMES: list[str] = [
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


def write_clips_csv(clips_data: list[dict], output_path: Path) -> None:
    """
    Write *clips_data* to a CSV file at *output_path*.

    Parameters
    ----------
    clips_data:
        List of dicts.  Expected keys:
        ``filename``, ``source_url_or_path`` (or ``source_url``), ``start``, ``end``,
        ``duration``, ``score``, ``transcript_snippet``, ``suggested_title``,
        ``suggested_description``, ``suggested_hashtags``.
        Any missing key is written as an empty string.
    output_path:
        Destination ``.csv`` file path.  Parent directories are created
        automatically.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=_CSV_FIELDNAMES,
            extrasaction="ignore",
        )
        writer.writeheader()
        for clip in clips_data:
            row = {}
            for field in _CSV_FIELDNAMES:
                val = clip.get(field, "")
                if val == "" and field == "source_url_or_path":
                    val = clip.get("source_url", "")
                row[field] = val
            writer.writerow(row)

    logger.info("CSV written: %s (%d clips)", output_path, len(clips_data))


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------


def _fmt_duration(seconds: float) -> str:
    """Format *seconds* as ``HH:MM:SS``."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def write_summary_md(
    source_name: str,
    source_url: str,
    clips_data: list[dict],
    output_path: Path,
    total_duration: float,
    processing_time: float,
) -> None:
    """
    Write a Markdown summary report to *output_path*.

    The report includes:
    - Source metadata (name, URL, total duration, processing time).
    - A table of all clips with key metrics.

    Parameters
    ----------
    source_name:
        Human-readable name of the source video.
    source_url:
        URL or file path of the source.
    clips_data:
        List of clip dicts (same schema as :func:`write_clips_csv`).
    output_path:
        Destination ``.md`` file path.
    total_duration:
        Total duration of the source video in seconds.
    processing_time:
        Wall-clock time taken to process the video (seconds).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# ClipFinder — Summary Report\n",
        f"**Source:** {source_name}  ",
        f"**URL:** {source_url}  ",
        f"**Total Duration:** {_fmt_duration(total_duration)}  ",
        f"**Processing Time:** {processing_time:.1f}s  ",
        f"**Clips Found:** {len(clips_data)}  \n",
        "---\n",
        "## Clips\n",
        "| # | Filename | Start | End | Duration | Score | Title |",
        "|---|----------|-------|-----|----------|-------|-------|",
    ]

    for idx, clip in enumerate(clips_data, start=1):
        filename         = clip.get("filename", "")
        start            = clip.get("start", 0.0)
        end              = clip.get("end", 0.0)
        duration         = clip.get("duration", end - start if end else 0.0)
        score            = clip.get("score", 0.0)
        suggested_title  = clip.get("suggested_title", "").replace("|", "\\|")

        lines.append(
            f"| {idx} | `{filename}` | {_fmt_duration(float(start))} | "
            f"{_fmt_duration(float(end))} | {_fmt_duration(float(duration))} | "
            f"{float(score):.3f} | {suggested_title} |"
        )

    lines.append("\n---\n")
    lines.append("## Clip Details\n")

    for idx, clip in enumerate(clips_data, start=1):
        filename    = clip.get("filename", f"clip_{idx}")
        title       = clip.get("suggested_title", "")
        description = clip.get("suggested_description", "")
        hashtags    = clip.get("suggested_hashtags", "")
        snippet     = clip.get("transcript_snippet", "")
        score       = clip.get("score", 0.0)

        lines.append(f"### {idx}. {title or filename}\n")
        lines.append(f"- **File:** `{filename}`")
        lines.append(f"- **Score:** {float(score):.4f}")
        if snippet:
            lines.append(f'- **Transcript:** "{snippet}"')
        if description:
            lines.append(f"- **Description:** {description}")
        if hashtags:
            lines.append(f"- **Hashtags:** {hashtags}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Summary markdown written: %s", output_path)


# ---------------------------------------------------------------------------
# Local metadata generation (no external API)
# ---------------------------------------------------------------------------

#: Simple English stop-words to exclude from keyword extraction.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "of",
        "and", "or", "but", "for", "with", "this", "that", "was",
        "are", "be", "been", "have", "has", "had", "do", "did", "does",
        "i", "you", "he", "she", "we", "they", "my", "your", "his",
        "her", "our", "its", "so", "if", "not", "no", "as", "up",
        "just", "like", "get", "got", "im", "its", "can", "will",
    }
)

#: Title / description templates keyed by preset name.
_TEMPLATES: dict[str, dict[str, str]] = {
    "general": {
        "title":       "{kw0} — {kw1} moments you need to see 🔥",
        "description": "Watch this incredible moment about {kw0} and {kw1}. {kw2} insights you can't miss!",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #shorts #viral #trending #gaming",
    },
    "gaming": {
        "title":       "🔥 {kw0} was INSANE! Unbelievable {kw1} play 🎮",
        "description": "You won't believe this {kw0} moment! Epic {kw1} and {kw2} highlight.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #gaming #gamer #gameplay #shorts #twitch #viral",
    },
    "funny": {
        "title":       "😂 BRO THIS GTA 6 MOMENT IS UNHINGED! ({kw0} {kw1})",
        "description": "I can't breathe watching this GTA 6 {kw0} glitch. Look at what happened with {kw1} and {kw2}!",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #GTAVI #GTA6Funny #GamingMemes #ViceCity #shorts #tiktok",
    },
    "serious": {
        "title":       "🤫 The Dark Truth About GTA 6's {kw0} Storyline ({kw1})",
        "description": "Lucia and Jason's story gets crazy here. Notice this hidden detail about {kw0} and {kw1}?",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #GTA6Lore #GTA6Story #Lucia #Jason #ViceCity #shorts",
    },
    "sad": {
        "title":       "💔 The Saddest GTA 6 Moment Nobody Was Ready For ({kw0})",
        "description": "This scene between {kw0} and {kw1} broke everyone. The music and dialogue about {kw2} hits so hard.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #GTA6Story #Emotional #GamingMoments #SadVibes #shorts",
    },
    "action": {
        "title":       "🔥 SURVIVING A 5-STAR WANTED LEVEL IN GTA 6! ({kw0} {kw1})",
        "description": "Total chaos in Vice City! Insane shootout using {kw0} against SWAT and {kw1}.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #GTA6Gameplay #ViceCity #5Stars #Gunfight #GamingShorts",
    },
    "chases": {
        "title":       "🚨 IMPOSSIBLE POLICE ESCAPE IN GTA 6! ({kw0} SPEEDRUN)",
        "description": "Full speed escape through Vice City with {kw0}. How did {kw1} and {kw2} even survive this jump?!",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #CarChase #PoliceChase #ViceCity #Supercars #shorts",
    },
    "cinematic": {
        "title":       "🌴 GTA 6 Vice City Graphics Look So Photorealistic ({kw0})",
        "description": "Cruising down Ocean Drive at sunset with {kw0} and {kw1}. The lighting and atmosphere in GTA 6 is unmatched.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #ViceCity #OceanDrive #RTX #Cinematic #shorts",
    },
    "stunts": {
        "title":       "😱 99.9% OF PLAYERS CAN'T DO THIS GTA 6 STUNT! ({kw0})",
        "description": "World first {kw0} stunt jump over {kw1}! The physics in GTA 6 are absolutely wild.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #GTA6 #GTA6Stunts #InsaneStunts #WTFMoments #GamingViral #shorts",
    },
    "podcast": {
        "title":       "🎙️ The truth about {kw0} nobody talks about ({kw1})",
        "description": "Deep dive into {kw0} and {kw1}. Why {kw2} changes the way you think.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #podcast #clips #insights #deepdive #shorts",
    },
    "motivational": {
        "title":       "🚀 {kw0}: the {kw1} mindset that changes everything",
        "description": "Unlock the power of {kw0}. {kw1} and {kw2} are the keys to your success.",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #motivation #mindset #success #shorts",
    },
    "educational": {
        "title":       "Did you know? {kw0} and {kw1} explained in seconds",
        "description": "Quick breakdown of {kw0}, {kw1}, and {kw2}. Perfect for learners!",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #education #learnontiktok #didyouknow #shorts",
    },
    "entertainment": {
        "title":       "{kw0} hits different when you understand {kw1} 🎬",
        "description": "Best {kw0} moment featuring {kw1} and {kw2}. Must watch!",
        "hashtags":    "#{kw0} #{kw1} #{kw2} #entertainment #fun #trending #shorts",
    },
}


def _extract_keywords(text: str, top_n: int = 3) -> list[str]:
    """
    Extract the top *top_n* keywords from *text* by word frequency,
    excluding stop-words and short tokens.

    Returns lower-cased keywords.  Falls back to ``["clip", "video", "shorts"]``
    if the text is too sparse.
    """
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    freq: dict[str, int] = {}
    for token in tokens:
        clean = token.strip("'")
        if len(clean) > 2 and clean not in _STOP_WORDS:
            freq[clean] = freq.get(clean, 0) + 1

    # Sort by frequency descending, then alphabetically for determinism
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    keywords = [kw for kw, _ in ranked[:top_n]]

    # Pad with generic fallbacks if not enough unique keywords
    fallbacks = ["clip", "video", "shorts", "content", "moment"]
    while len(keywords) < top_n:
        for fb in fallbacks:
            if fb not in keywords:
                keywords.append(fb)
            if len(keywords) >= top_n:
                break

    return keywords[:top_n]


def generate_local_metadata(
    transcript_snippet: str,
    hook_words: list[str],
    score: float,
    preset: str = "general",
) -> dict:
    """
    Generate title, description, and hashtags from a transcript snippet using
    keyword templates.  No external API required.

    Parameters
    ----------
    transcript_snippet:
        A short excerpt of the transcribed speech for this clip.
    hook_words:
        High-scoring hook words detected in the clip (used to bias keywords).
    score:
        Clip engagement score (0–1); currently used for future score-aware
        template selection (e.g. promote high-score clips differently).
    preset:
        Template preset — one of ``"general"``, ``"motivational"``,
        ``"educational"``, ``"entertainment"``.

    Returns
    -------
    dict
        ``{suggested_title, suggested_description, suggested_hashtags}``
    """
    # Combine snippet and hook words for keyword extraction
    combined_text = transcript_snippet + " " + " ".join(hook_words)
    keywords = _extract_keywords(combined_text, top_n=3)

    # Capitalise for display
    kw0, kw1, kw2 = [kw.capitalize() for kw in keywords]

    # Select template (fall back to general)
    templates = _TEMPLATES.get(preset, _TEMPLATES["general"])

    def render(tmpl: str) -> str:
        return tmpl.format(kw0=kw0, kw1=kw1, kw2=kw2)

    return {
        "suggested_title":       render(templates["title"]),
        "suggested_description": render(templates["description"]),
        "suggested_hashtags":    render(templates["hashtags"]),
    }


# ---------------------------------------------------------------------------
# Gemini enhancement (optional)
# ---------------------------------------------------------------------------


def try_gemini_enhance(
    clips_data: list[dict],
    source_context: str,
    api_key: str | None = None,
) -> list[dict]:
    """
    Optionally re-rank clips and improve their titles/descriptions using the
    Gemini API.

    If neither the *api_key* parameter nor ``GEMINI_API_KEY`` environment variable
    is provided, or if any network error occurs, the function returns *clips_data*
    unchanged (100% offline fallback).

    Uses ``gemini-1.5-flash`` (free tier).
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        logger.debug("GEMINI_API_KEY not set; skipping Gemini enhancement.")
        return clips_data

    # Try official google.generativeai first if installed
    try:
        import google.generativeai as genai  # type: ignore[import-untyped]
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        enhanced: list[dict] = []
        for clip in clips_data:
            snippet = clip.get("transcript_snippet", "")
            current_title = clip.get("suggested_title", "")
            prompt = (
                f"You are a short-form video content expert for GTA 6 and gaming clips.\n"
                f"Source video context: {source_context}\n"
                f"Transcript snippet: \"{snippet}\"\n"
                f"Current suggested title: \"{current_title}\"\n\n"
                "Respond ONLY with a JSON object containing exactly these keys:\n"
                '{"suggested_title": "...", "suggested_description": "...", "suggested_hashtags": "..."}\n'
                "Make the title catchy and viral for TikTok/Reels/Shorts, the description engaging, "
                "and include 5-8 relevant hashtags like #GTA6 #GTAVI #ViceCity #shorts."
            )
            response = model.generate_content(prompt)
            raw = response.text.strip()
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                import json
                try:
                    updates = json.loads(json_match.group())
                    enhanced.append({**clip, **updates})
                    continue
                except json.JSONDecodeError:
                    pass
            enhanced.append(clip)
            time.sleep(0.5)
        return enhanced
    except Exception as exc:
        logger.debug("google.generativeai failed (%s) — trying lightweight REST fallback", exc)

    # Lightweight direct REST fallback via requests (works on all Python versions without extra packages)
    try:
        import json
        import requests

        enhanced = []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        for clip in clips_data:
            snippet = clip.get("transcript_snippet", "")
            current_title = clip.get("suggested_title", "")
            prompt = (
                f"You are a viral short-form video creator for GTA 6 / gaming clips.\n"
                f"Source video context: {source_context}\n"
                f"Transcript snippet: \"{snippet}\"\n"
                f"Current title: \"{current_title}\"\n\n"
                "Respond ONLY with a JSON object containing exactly these keys:\n"
                '{"suggested_title": "...", "suggested_description": "...", "suggested_hashtags": "..."}\n'
                "Make the title super viral for TikTok/Shorts/Reels, the description engaging, and include #GTA6 #ViceCity #shorts."
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4}
            }
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                raw = data["candidates"][0]["content"]["parts"][0]["text"]
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    updates = json.loads(json_match.group())
                    enhanced.append({**clip, **updates})
                    continue
            enhanced.append(clip)
            time.sleep(0.5)
        return enhanced
    except Exception as exc:
        logger.warning("Gemini REST request failed: %s; keeping original local metadata.", exc)
        return clips_data


# ---------------------------------------------------------------------------
# ZIP archive
# ---------------------------------------------------------------------------

#: File extensions to include in the output zip.
_ZIP_EXTENSIONS: tuple[str, ...] = (".mp4", ".srt", ".ass", ".csv", ".md")


def create_zip(source_dir: Path, output_zip: Path) -> Path:
    """
    Create a zip archive of all ``.mp4``, ``.srt``, ``.ass``, ``.csv``, and
    ``.md`` files in *source_dir*.

    Parameters
    ----------
    source_dir:
        Directory to scan for output files.
    output_zip:
        Destination ``.zip`` file path.  Parent directories are created
        automatically.

    Returns
    -------
    Path
        Path to the created zip archive.
    """
    source_dir = Path(source_dir)
    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in _ZIP_EXTENSIONS:
            for file_path in sorted(source_dir.glob(f"*{ext}")):
                zf.write(file_path, arcname=file_path.name)
                logger.debug("Added to zip: %s", file_path.name)

    logger.info("Zip archive created: %s", output_zip)
    return output_zip
