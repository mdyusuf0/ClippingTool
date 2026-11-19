"""ClipFinder — ingest: input classification, ffprobe, and permission gate."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from clipfinder.cancellation import cancellation_token, CancellationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input classification
# ---------------------------------------------------------------------------

_YOUTUBE_RE = re.compile(
    r"(https?://)?([a-zA-Z0-9_\-]+\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|live$)|youtu\.be/)",
    re.IGNORECASE,
)
_KICK_RE = re.compile(r"(https?://)?([a-zA-Z0-9_\-]+\.)?kick\.com/", re.IGNORECASE)
_GDRIVE_RE = re.compile(r"https?://drive\.google\.com/", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".ts", ".wmv"}


def classify_input(item: str) -> tuple[str, str]:
    """
    Classify *item* as one of: ``youtube``, ``kick``, ``gdrive``, ``url``, ``file``, ``dir``.

    Returns ``(kind, resolved)`` where *resolved* is the same string
    (URLs are unchanged; local paths are resolved to absolute strings).
    """
    if _YOUTUBE_RE.search(item):
        return "youtube", item
    if _KICK_RE.search(item):
        return "kick", item
    if _GDRIVE_RE.search(item):
        return "gdrive", item
    if _URL_RE.match(item):
        return "url", item

    path = Path(item).resolve()
    if path.is_dir():
        return "dir", str(path)
    return "file", str(path)


# ---------------------------------------------------------------------------
# ffprobe
# ---------------------------------------------------------------------------

def probe_video(path: Path) -> dict[str, Any]:
    """
    Run ffprobe on *path* and return a dict with keys:

    - ``duration`` (float, seconds)
    - ``width`` (int)
    - ``height`` (int)
    - ``has_audio`` (bool)
    - ``codec_name`` (str)
    - ``fps`` (float)
    - ``raw`` (the full ffprobe JSON output)

    Raises ``RuntimeError`` on ffprobe failure or missing streams.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found on PATH — install ffmpeg.")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream: dict[str, Any] = {}
    has_audio = False

    for s in streams:
        if s.get("codec_type") == "video" and not video_stream:
            video_stream = s
        elif s.get("codec_type") == "audio":
            has_audio = True

    if not video_stream:
        raise RuntimeError(f"No video stream found in {path}")

    # Duration: prefer format-level, fall back to stream
    duration = float(
        fmt.get("duration")
        or video_stream.get("duration")
        or 0.0
    )

    # FPS from avg_frame_rate "30/1" or "30000/1001"
    fps_raw = video_stream.get("avg_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    return {
        "duration": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "has_audio": has_audio,
        "codec_name": video_stream.get("codec_name", "unknown"),
        "fps": fps,
        "raw": data,
    }


# ---------------------------------------------------------------------------
# collect_inputs & permission_gate & download
# ---------------------------------------------------------------------------

def collect_inputs_from_dir(directory: Path) -> list[Path]:
    """Return all video files directly inside *directory* (non-recursive)."""
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in _VIDEO_EXTS)


def collect_inputs(
    positional: list[str],
    links_file: str | None = None,
    max_source_hours: float | None = None,
    playlist_items: str | None = None,
) -> list[dict[str, Any]]:
    """Collect and classify all input sources into a list of source dicts."""
    raw: list[str] = list(positional)

    if links_file:
        lf = Path(links_file)
        if not lf.exists():
            logger.error("--links-file not found: %s", lf)
        else:
            lines = [
                ln.strip()
                for ln in lf.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")
            ]
            raw.extend(lines)

    sources: list[dict[str, Any]] = []
    for item in raw:
        kind, resolved = classify_input(item)
        entry: dict[str, Any] = {"raw": item, "kind": kind, "resolved": resolved}
        if playlist_items:
            entry["playlist_items"] = playlist_items
        sources.append(entry)

    logger.info("Collected %d source(s).", len(sources))
    return sources


def permission_gate(
    sources: list[dict[str, Any]] | list[str],
    has_permission_flag: bool,
    interactive: bool = True,
) -> bool:
    """
    For URL sources, verify the user has rights to download/process them.
    Returns True to continue, False to abort.
    """
    url_sources: list[str] = []
    for s in sources:
        if isinstance(s, str):
            kind, _ = classify_input(s)
            if kind in ("youtube", "kick", "url", "gdrive"):
                url_sources.append(s)
        elif isinstance(s, dict) and s.get("kind") in ("youtube", "kick", "url", "gdrive"):
            url_sources.append(s.get("raw", ""))

    if not url_sources:
        return True  # only local files, no gate needed

    if has_permission_flag:
        logger.info("Permission confirmed via flag or confirmation checkbox.")
        return True

    if not interactive:
        logger.warning(
            "URL sources detected but --i-have-permission not set and not running interactively."
        )
        return False

    from rich.console import Console

    console = Console()
    console.print(
        "\n[bold yellow]⚠  Online Source Notice[/bold yellow]\n"
        "You are about to download content from external URLs.\n"
        "By proceeding you confirm that:\n"
        "  • You own or have permission to use this content, [bold]and[/bold]\n"
        "  • You comply with the platform's Terms of Service.\n"
    )
    try:
        answer = input("Do you have permission to download and use this content? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if answer in ("y", "yes"):
        return True

    console.print("[red]Aborted — no permission granted.[/red]")
    return False


def download_source(
    source: dict[str, Any] | str,
    out_dir: Path,
    config: dict[str, Any] | None = None,
) -> Path | None:
    """
    Download a URL source using yt-dlp or gdown. Returns local path or None on failure.
    Supports YouTube, Kick.com, Google Drive, and direct video URLs.
    """
    cfg = config or {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(source, str):
        kind, resolved = classify_input(source)
        source_dict: dict[str, Any] = {"raw": source, "kind": kind, "resolved": resolved}
    else:
        source_dict = source

    kind = source_dict.get("kind", "")
    url = source_dict.get("raw", "")

    if kind == "file":
        p = Path(source_dict.get("resolved", url))
        return p if p.exists() else None

    # Google Drive download via gdown
    if kind == "gdrive":
        try:
            import gdown

            dl_file = out_dir / "gdrive_video.mp4"
            gdown.download(url, str(dl_file), quiet=not cfg.get("verbose", False), fuzzy=True)
            if dl_file.exists():
                return dl_file
        except Exception as exc:
            logger.error("gdown failed for %s: %s", url, exc)
            return None

    # yt-dlp for YouTube, Kick, and generic stream URLs
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        logger.error("yt-dlp is not installed. Run: pip install yt-dlp")
        return None

    # Probe first without downloading to detect live streams / status
    probe_opts: dict[str, Any] = {
        "quiet": not cfg.get("verbose", False),
        "no_warnings": not cfg.get("verbose", False),
    }

    is_live = False
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl_probe:
            info_probe = ydl_probe.extract_info(url, download=False)
            if info_probe:
                # Handle search results or playlists where entries is a list
                if "entries" in info_probe and info_probe["entries"]:
                    target_info = info_probe["entries"][0]
                else:
                    target_info = info_probe

                is_live = bool(target_info.get("is_live") or target_info.get("live_status") == "is_live")
                if target_info.get("live_status") == "is_upcoming":
                    logger.warning("Stream is upcoming / scheduled and has not started yet: %s", url)
                    return None
    except Exception as exc:
        logger.debug("Live stream probe check failed: %s; proceeding with standard download", exc)

    cancellation_token.check_canceled()

    def _ydl_cancel_hook(d: dict[str, Any]) -> None:
        if cancellation_token.is_canceled():
            raise CancellationError("Download canceled by user.")

    ydl_opts: dict[str, Any] = {
        "outtmpl": str(out_dir / "%(title).50s.%(ext)s"),
        "quiet": not cfg.get("verbose", False),
        "no_warnings": not cfg.get("verbose", False),
        "progress_hooks": [_ydl_cancel_hook],
    }

    if is_live:
        live_duration_min = float(cfg.get("live_duration", cfg.get("live_capture_minutes", 2.0)))
        capture_sec = int(max(live_duration_min * 60, 5))
        live_from_start = bool(cfg.get("live_from_start", False))
        logger.info(
            "Detected active Live Stream! Capturing %d seconds (%0.1f min) with ffmpeg: %s",
            capture_sec, live_duration_min, url,
        )
        ydl_opts["format"] = "bestvideo*+bestaudio/best"
        ydl_opts["live_from_start"] = live_from_start
        ydl_opts["external_downloader"] = "ffmpeg"
        ydl_opts["external_downloader_args"] = {"ffmpeg": ["-t", str(capture_sec)]}
    else:
        ydl_opts["format"] = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        if cfg.get("playlist_items"):
            ydl_opts["playlist_items"] = cfg["playlist_items"]
        if cfg.get("max_source_hours"):
            ydl_opts["match_filter"] = yt_dlp.utils.match_filter_func(
                f"duration <= {int(cfg['max_source_hours'] * 3600)}"
            )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            cancellation_token.check_canceled()
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            target = info["entries"][0] if "entries" in info and info["entries"] else info
            fname = ydl.prepare_filename(target)
            p = Path(fname)
            if p.exists() and p.stat().st_size > 0:
                return p
            # If ext differed or external downloader produced a different filename
            for f in sorted(out_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file() and f.suffix.lower() in _VIDEO_EXTS and f.stat().st_size > 0:
                    return f
            return None
    except CancellationError:
        raise
    except Exception as exc:
        if cancellation_token.is_canceled():
            raise CancellationError("Download canceled by user.")
        logger.error("Download failed for %s: %s", url, exc)
        return None


# Alias for backwards compatibility
download_url = download_source

