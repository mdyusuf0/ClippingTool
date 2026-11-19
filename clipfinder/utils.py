"""ClipFinder — utils: filename sanitisation and other shared helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import unicodedata
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_FILENAME_LEN = 80  # max chars for sanitized names


def sanitize_filename(raw: str, max_len: int = _MAX_FILENAME_LEN) -> str:
    """
    Produce a filesystem-safe name from an arbitrary string.

    Steps:
      1. Unicode NFKD normalisation then encode to ASCII (lossy).
      2. Remove emoji and non-printable characters.
      3. Replace runs of whitespace / unsafe chars with underscores.
      4. Strip leading/trailing underscores and dots.
      5. Truncate to *max_len* characters.
      6. Fall back to 'untitled' if the result is empty.
    """
    # Normalise unicode
    name = unicodedata.normalize("NFKD", raw)
    # Encode to ASCII, ignore non-ASCII bytes
    name = name.encode("ascii", errors="ignore").decode("ascii")

    # Remove characters unsafe on Windows / macOS / Linux filesystems
    # Keep alphanumerics, spaces, hyphens, dots, underscores, parens
    name = re.sub(r"[^\w\s\-.()\[\]]", "", name)

    # Collapse whitespace → single underscore
    name = re.sub(r"[\s_]+", "_", name).strip("_.")

    # Truncate
    name = name[:max_len].rstrip("_.")

    return name or "untitled"


def sha256_file(path: Path) -> str:
    """Read a file in 8 MB chunks and return its hexadecimal SHA-256 digest."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def estimate_disk_mb(duration_s: float, streams: int = 2) -> float:
    """Estimate disk space needed in megabytes for intermediate and rendered files."""
    return max(50.0, float(duration_s * streams * 2.0))


def download_noto_font(fonts_dir: Path | None = None) -> Path | None:
    """
    Download NotoSans-Regular.ttf (OFL free font with broad script coverage)
    to fonts_dir if not present. Returns Path on success, None on error.
    """
    if fonts_dir is None:
        fonts_dir = Path.home() / ".cache" / "clipfinder" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    font_path = fonts_dir / "NotoSans-Regular.ttf"
    if font_path.exists() and font_path.stat().st_size > 1000:
        return font_path

    url = "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClipFinder/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response, open(font_path, "wb") as out_file:
            out_file.write(response.read())
        logger.info("Downloaded Noto Sans font to %s", font_path)
        return font_path
    except Exception as exc:
        logger.debug("Could not download Noto Sans font: %s", exc)
        return None


def get_system_font_fallback() -> str:
    """Return a ubiquitous system font name based on the current OS."""
    system = platform.system()
    if system == "Windows":
        return "Arial"
    elif system == "Darwin":
        return "Helvetica"
    else:
        return "DejaVu Sans"


def human_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{s}s"
