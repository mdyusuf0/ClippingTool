#!/usr/bin/env python3
"""ClipFinder - Extract viral short clips from long-form video."""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import yaml

# Force UTF-8 output on Windows so Rich box-drawing / emoji chars don't crash
# the legacy cp1252 console. This must happen before any Rich import.
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Logging setup (file + console)
# ---------------------------------------------------------------------------

logger = logging.getLogger("clipfinder")


def _setup_logging(out_dir: Path, verbose: bool) -> None:
    """Configure root logger to write to console and a log file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "clipfinder.log"

    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)

    logger.debug("Log file: %s", log_path)


# ---------------------------------------------------------------------------
# Config loading and merging
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config(config_path: Path | None) -> dict[str, Any]:
    """Load YAML config file; fall back to default bundled config."""
    path = config_path if config_path is not None else _DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.warning("Config file not found: %s — using built-in defaults.", path)
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    logger.debug("Loaded config from %s", path)
    return data


def _merge_config(cfg: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """
    Priority (highest → lowest):
      CLI args > preset overrides > config defaults > argparse defaults
    """
    defaults = cfg.get("defaults", {})

    # Apply preset first
    preset_name = args.preset
    if preset_name:
        preset_data = cfg.get("presets", {}).get(preset_name, {})
        if not preset_data:
            logger.warning("Preset '%s' not found in config — ignoring.", preset_name)
        else:
            logger.info("Applying preset: %s", preset_name)
            defaults.update(preset_data)

    # Argparse sentinel: use object identity trick — only override when user
    # actually passed the flag (i.e. the value differs from None).
    cli_map = {
        "clips": args.clips,
        "min": args.min,
        "max": args.max,
        "output": args.out,
        "model": args.model,
        "language": args.lang,
        "style": args.style,
        "captions": args.captions,
    }
    for key, val in cli_map.items():
        if val is not None:
            defaults[key] = val

    # Boolean flags
    defaults["no_captions"] = args.no_captions
    defaults["dry_run"] = args.dry_run
    defaults["keep_temp"] = args.keep_temp
    defaults["resume"] = args.resume
    defaults["verbose"] = args.verbose
    defaults["translate_to_english"] = args.translate_to_english
    defaults["mask_profanity"] = args.mask_profanity
    defaults["i_have_permission"] = args.i_have_permission

    # Optional scalar args
    if args.hook_text is not None:
        defaults["hook_text"] = args.hook_text
    if args.start is not None:
        defaults["start"] = args.start
    if args.end is not None:
        defaults["end"] = args.end
    if args.max_source_hours is not None:
        defaults["max_source_hours"] = args.max_source_hours
    if args.playlist_items is not None:
        defaults["playlist_items"] = args.playlist_items
    if getattr(args, "live_duration", None) is not None:
        defaults["live_duration"] = args.live_duration
    if getattr(args, "live_from_start", False):
        defaults["live_from_start"] = args.live_from_start

    # Carry full config sections through for later use
    defaults["_scoring_weights"] = cfg.get("scoring_weights", {})
    defaults["_scene_change_threshold"] = cfg.get("scene_change_threshold", 0.3)
    defaults["_vad_filter"] = cfg.get("vad_filter", True)
    defaults["_word_timestamps"] = cfg.get("word_timestamps", True)
    defaults["_chunk_hours"] = cfg.get("chunk_hours", 2.5)
    defaults["_cache_transcripts"] = cfg.get("cache_transcripts", True)
    defaults["_presets"] = cfg.get("presets", {})

    # Resolve preset hook_words list
    if preset_name:
        hw = defaults.get("hook_words", [])
        defaults["hook_words"] = hw

    return defaults


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clipfinder",
        description="ClipFinder — Extract viral short clips from long-form video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional
    p.add_argument(
        "inputs",
        nargs="*",
        metavar="INPUT",
        help="Files, folders, or URLs to process.",
    )

    # Core clip options
    p.add_argument("--clips", type=int, default=None, metavar="N", help="Number of clips to extract (default: 5).")
    p.add_argument("--min", type=int, default=None, metavar="SECONDS", help="Minimum clip duration in seconds (default: 15).")
    p.add_argument("--max", type=int, default=None, metavar="SECONDS", help="Maximum clip duration in seconds (default: 45).")
    p.add_argument("--out", default=None, metavar="PATH", help="Output directory (default: output/).")

    # Transcription
    p.add_argument("--model", default=None, metavar="NAME", help="Whisper model: tiny|base|small|medium|large-v2 (default: base).")
    p.add_argument("--lang", "--language", dest="lang", default=None, metavar="CODE", help="Source language code or 'auto' (default: auto).")
    p.add_argument("--translate-to-english", action="store_true", help="Translate non-English audio to English captions.")

    # Rendering
    p.add_argument("--style", default=None, choices=["blur", "crop", "facecrop"], help="Vertical reframe style (default: blur).")
    p.add_argument("--captions", default=None, choices=["bold", "pop", "vice_city", "minimal"], help="Caption style preset (default: bold).")
    p.add_argument("--no-captions", action="store_true", help="Disable subtitle burning.")

    # Content / scoring
    p.add_argument("--preset", default=None, metavar="NAME", help="Named preset: gaming | podcast | general.")
    p.add_argument("--hook-text", default=None, metavar="TEXT", help="Custom hook-word to prepend to scoring vocabulary.")
    p.add_argument("--mask-profanity", action="store_true", help="Bleep/mask profanity in captions.")

    # Trimming
    p.add_argument("--start", type=float, default=None, metavar="SECONDS", help="Ignore video content before this timestamp.")
    p.add_argument("--end", type=float, default=None, metavar="SECONDS", help="Ignore video content after this timestamp.")
    p.add_argument("--max-source-hours", type=float, default=None, metavar="HOURS", help="Skip sources longer than this many hours.")

    # Online sources
    p.add_argument("--links-file", default=None, metavar="PATH", help="Text file with one URL or path per line.")
    p.add_argument("--i-have-permission", action="store_true", help="Confirm you have rights to download/process URLs.")
    p.add_argument("--playlist-items", default=None, metavar="SPEC", help="yt-dlp playlist item spec, e.g. '1-5'.")
    p.add_argument(
        "--live-duration",
        "--live-capture-minutes",
        dest="live_duration",
        type=float,
        default=None,
        metavar="MINUTES",
        help="Duration in minutes to capture from an active live stream (default: 2.0).",
    )
    p.add_argument(
        "--live-from-start",
        action="store_true",
        help="Download YouTube live stream from the beginning if DVR rewind is supported.",
    )

    # Workflow
    p.add_argument("--dry-run", action="store_true", help="Score and show clips without rendering.")
    p.add_argument("--keep-temp", action="store_true", help="Keep temporary download/processing files.")
    p.add_argument("--resume", action="store_true", help="Skip clips already present in the output directory.")

    # UI / config
    p.add_argument("--ui", action="store_true", help="Launch the Gradio web UI instead of CLI processing.")
    p.add_argument("--config", default=None, metavar="PATH", help="Path to a custom YAML config file.")
    p.add_argument("--verbose", action="store_true", help="Enable debug-level logging.")

    return p


# ---------------------------------------------------------------------------
# Stub implementations (replace with real module imports)
# ---------------------------------------------------------------------------

def run_preflight() -> bool:
    """Check ffmpeg, ffprobe, disk space, Python version. Return False on failure."""
    import shutil

    ok = True

    # Python version
    if sys.version_info < (3, 9):
        logger.error("Python 3.9+ is required (got %s).", sys.version.split()[0])
        ok = False

    # ffmpeg / ffprobe
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            logger.error(
                "'%s' not found on PATH. Install ffmpeg: "
                "Windows: `winget install ffmpeg`  macOS: `brew install ffmpeg`  "
                "Linux: `sudo apt install ffmpeg`",
                tool,
            )
            ok = False

    # Disk space (warn if < 2 GB free on output drive)
    try:
        import shutil as _shutil

        stat = _shutil.disk_usage(Path.cwd())
        free_gb = stat.free / (1024 ** 3)
        if free_gb < 2.0:
            logger.warning("Low disk space: %.1f GB free — may fail during render.", free_gb)
    except Exception:
        pass

    return ok


def launch_ui(config: dict[str, Any]) -> None:  # pragma: no cover
    """Launch the Gradio web UI."""
    try:
        from clipfinder.ui import launch_ui as _launch_ui
        _launch_ui(default_config=config)
    except ImportError:
        logger.error("Gradio is not installed. Run: pip install gradio")
        sys.exit(1)


def collect_inputs(
    positional: list[str],
    links_file: str | None,
    max_source_hours: float | None,
    playlist_items: str | None,
) -> list[dict[str, Any]]:
    """Collect and classify all input sources into a list of dicts."""
    from clipfinder.ingest import classify_input

    raw: list[str] = list(positional)

    if links_file:
        lf = Path(links_file)
        if not lf.exists():
            logger.error("--links-file not found: %s", lf)
        else:
            lines = [ln.strip() for ln in lf.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
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
    sources: list[dict[str, Any]],
    has_permission_flag: bool,
    interactive: bool = True,
) -> bool:
    """
    For URL sources, verify the user has rights to download/process them.
    Returns True to continue, False to abort.
    """
    url_sources = [s for s in sources if s["kind"] in ("youtube", "kick", "url", "gdrive")]
    if not url_sources:
        return True  # only local files, no gate needed

    if has_permission_flag:
        logger.info("Permission confirmed via --i-have-permission flag.")
        return True

    if not interactive:
        logger.warning("URL sources detected but --i-have-permission not set and not running interactively.")
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


def probe_video(path: Path) -> dict[str, Any]:
    """Run ffprobe and return stream info dict."""
    from clipfinder.ingest import probe_video as _probe

    return _probe(path)


def transcribe_video(
    path: Path,
    model_name: str,
    language: str,
    translate: bool,
    vad_filter: bool,
    word_timestamps: bool,
    chunk_hours: float,
    cache: bool,
    out_dir: Path,
) -> list[dict[str, Any]]:
    """Transcribe video and return list of word dicts with start/end/text keys."""
    from clipfinder.transcribe import transcribe_video as _transcribe

    return _transcribe(
        path=path,
        model_name=model_name,
        language=language,
        translate=translate,
        vad_filter=vad_filter,
        word_timestamps=word_timestamps,
        chunk_hours=chunk_hours,
        cache=cache,
        out_dir=out_dir,
    )


def detect_scene_changes(path: Path, threshold: float) -> list[float]:
    """Return list of timestamps (seconds) where scene changes occur."""
    from clipfinder.score import detect_scene_changes as _dsc

    return _dsc(path, threshold)


def compute_audio_energy(path: Path) -> list[tuple[float, float]]:
    """Return list of (time_seconds, rms_energy) tuples."""
    from clipfinder.score import compute_audio_energy as _cae

    return _cae(path)


def score_clips(
    words: list[dict[str, Any]],
    audio_energy: list[tuple[float, float]],
    scene_changes: list[float],
    hook_words: list[str],
    min_dur: int,
    max_dur: int,
    top_n: int,
    scoring_weights: dict[str, float],
    video_duration: float,
) -> list[dict[str, Any]]:
    """Score and return top N non-overlapping clip windows."""
    from clipfinder.score import score_clips as _sc

    return _sc(
        words=words,
        audio_energy=audio_energy,
        scene_changes=scene_changes,
        hook_words=hook_words,
        min_dur=min_dur,
        max_dur=max_dur,
        top_n=top_n,
        scoring_weights=scoring_weights,
        video_duration=video_duration,
    )


def render_clip(
    source: Path,
    start: float,
    end: float,
    out_path: Path,
    style: str,
    crf: int,
    preset: str,
    audio_bitrate: str,
    ass_path: Path | None = None,
    hook_text: str | None = None,
) -> bool:
    """Render a single clip. Returns True on success."""
    from clipfinder.render import render_clip as _rc

    return _rc(
        source=source,
        start=start,
        end=end,
        out_path=out_path,
        style=style,
        crf=crf,
        preset=preset,
        audio_bitrate=audio_bitrate,
        ass_path=ass_path,
        hook_text=hook_text,
    )


def build_captions(
    words: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    out_stem: Path,
    style: str,
    mask_profanity: bool,
    translate: bool,
) -> tuple[Path | None, Path | None]:
    """Build .srt and .ass caption files. Returns (srt_path, ass_path)."""
    from clipfinder.captions import build_srt_file, build_ass_file, group_words

    clip_words = [
        {**w, "start": w["start"] - clip_start, "end": w["end"] - clip_start}
        for w in words
        if clip_start <= w.get("start", 0) < clip_end
    ]

    groups = group_words(clip_words, max_per_group=5)
    duration = clip_end - clip_start

    srt_path = out_stem.with_suffix(".srt")
    ass_path = out_stem.with_suffix(".ass")

    build_srt_file(groups, srt_path, mask_profanity=mask_profanity)
    build_ass_file(groups, ass_path, style=style, duration=duration, mask_profanity=mask_profanity)

    return srt_path, ass_path


def write_clips_csv(
    clips: list[dict[str, Any]],
    out_dir: Path,
    source_url_or_path: str = "",
    words: list[dict[str, Any]] | None = None,
    hook_words: list[str] | None = None,
    preset: str = "general",
) -> Path:
    """Write clips.csv with full clip metadata."""
    from clipfinder.output import (
        write_clips_csv as _write_csv,
        generate_local_metadata,
        try_gemini_enhance,
    )

    words_list = words or []
    hook_list = hook_words or []
    clips_data: list[dict[str, Any]] = []

    for idx, clip in enumerate(clips, 1):
        c_start = float(clip.get("start", 0.0))
        c_end = float(clip.get("end", 0.0))
        dur = c_end - c_start
        out_f = clip.get("output_file", f"clip_{idx:02d}.mp4")

        snippet_words = [
            w.get("text", "") for w in words_list
            if c_start <= w.get("start", 0.0) < c_end
        ]
        snippet = " ".join(snippet_words).strip()

        meta = generate_local_metadata(
            transcript_snippet=snippet,
            hook_words=hook_list,
            score=float(clip.get("score", 0.0)),
            preset=preset,
        )

        entry = {
            "filename": Path(out_f).name,
            "source_url_or_path": source_url_or_path,
            "start": f"{c_start:.2f}",
            "end": f"{c_end:.2f}",
            "duration": f"{dur:.2f}",
            "score": f"{float(clip.get('score', 0.0)):.4f}",
            "transcript_snippet": snippet,
            "suggested_title": meta.get("suggested_title", ""),
            "suggested_description": meta.get("suggested_description", ""),
            "suggested_hashtags": meta.get("suggested_hashtags", ""),
        }
        clips_data.append(entry)

    source_name = Path(source_url_or_path).stem if source_url_or_path else "video"
    clips_data = try_gemini_enhance(clips_data, source_context=source_name)

    csv_path = out_dir / "clips.csv"
    _write_csv(clips_data, csv_path)
    return csv_path


def write_summary_md(
    source_name: str,
    clips: list[dict[str, Any]],
    out_dir: Path,
    config: dict[str, Any],
    source_url_or_path: str = "",
    video_duration: float = 0.0,
    processing_time: float = 0.0,
    words: list[dict[str, Any]] | None = None,
    hook_words: list[str] | None = None,
    preset: str = "general",
) -> Path:
    """Write summary.md with processing metadata and clip table."""
    from clipfinder.output import (
        write_summary_md as _write_md,
        generate_local_metadata,
        try_gemini_enhance,
    )

    words_list = words or []
    hook_list = hook_words or []
    clips_data: list[dict[str, Any]] = []

    for idx, clip in enumerate(clips, 1):
        c_start = float(clip.get("start", 0.0))
        c_end = float(clip.get("end", 0.0))
        dur = c_end - c_start
        out_f = clip.get("output_file", f"clip_{idx:02d}.mp4")

        snippet_words = [
            w.get("text", "") for w in words_list
            if c_start <= w.get("start", 0.0) < c_end
        ]
        snippet = " ".join(snippet_words).strip()

        meta = generate_local_metadata(
            transcript_snippet=snippet,
            hook_words=hook_list,
            score=float(clip.get("score", 0.0)),
            preset=preset,
        )

        entry = {
            "filename": Path(out_f).name,
            "source_url_or_path": source_url_or_path,
            "start": c_start,
            "end": c_end,
            "duration": dur,
            "score": float(clip.get("score", 0.0)),
            "transcript_snippet": snippet,
            "suggested_title": meta.get("suggested_title", ""),
            "suggested_description": meta.get("suggested_description", ""),
            "suggested_hashtags": meta.get("suggested_hashtags", ""),
        }
        clips_data.append(entry)

    clips_data = try_gemini_enhance(clips_data, source_context=source_name)

    md_path = out_dir / "summary.md"
    _write_md(
        source_name=source_name,
        source_url=source_url_or_path,
        clips_data=clips_data,
        output_path=md_path,
        total_duration=video_duration,
        processing_time=processing_time,
    )
    return md_path
    return md_path


def _print_clip_table(clips: list[dict[str, Any]], source_name: str) -> None:
    """Pretty-print clip table using rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"[bold cyan]ClipFinder -- {source_name}[/bold cyan]", show_lines=True)
    table.add_column("#", style="bold", justify="right", width=4)
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Hook Words Found", no_wrap=False)

    for i, clip in enumerate(clips, 1):
        start = clip.get("start", 0)
        end = clip.get("end", 0)
        dur = end - start
        score = clip.get("score", 0)
        hooks = ", ".join(clip.get("matched_hooks", [])) or "-"
        table.add_row(
            str(i),
            f"{start:.1f}s",
            f"{end:.1f}s",
            f"{dur:.1f}s",
            f"{score:.3f}",
            hooks,
        )

    console.print(table)


def _print_final_summary(results: list[dict[str, Any]]) -> None:
    """Print a final batch summary table."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="[bold green]ClipFinder -- Batch Complete[/bold green]", show_lines=True)
    table.add_column("Source", no_wrap=False)
    table.add_column("Status", justify="center")
    table.add_column("Clips", justify="right")
    table.add_column("Output Dir", no_wrap=False)

    for r in results:
        status_str = "[green]OK[/green]" if r["ok"] else "[red]Error[/red]"
        table.add_row(r["source"], status_str, str(r.get("clips", 0)), r.get("out_dir", "-"))

    console.print(table)


def _download_url(source: dict[str, Any], out_dir: Path, config: dict[str, Any]) -> Path | None:
    """Download a URL source (supports live YouTube/Kick streams, VODs, Google Drive, direct URLs)."""
    from clipfinder.ingest import download_source

    return download_source(source, out_dir, config)


def _sanitize_name(raw: str) -> str:
    """Return a filesystem-safe directory name from a source string."""
    from clipfinder.utils import sanitize_filename

    return sanitize_filename(raw)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- Early: determine output dir for logging
    cfg_raw = _load_config(Path(args.config) if args.config else None)
    defaults = cfg_raw.get("defaults", {})
    out_dir = Path(args.out or defaults.get("output", "output/"))

    _setup_logging(out_dir, verbose=args.verbose)

    # --- Merge full config
    config = _merge_config(cfg_raw, args)

    # --- Re-resolve out_dir from merged config
    out_dir = Path(config.get("output", "output/"))

    # --- Preflight checks
    if not run_preflight():
        logger.error("Preflight checks failed — aborting.")
        return 1

    # --- UI mode
    if args.ui:
        launch_ui(config)
        return 0

    # --- Collect inputs
    sources = collect_inputs(
        positional=args.inputs or [],
        links_file=args.links_file,
        max_source_hours=config.get("max_source_hours"),
        playlist_items=config.get("playlist_items"),
    )

    if not sources:
        logger.error(
            "No inputs provided. Specify files/folders/URLs as positional args "
            "or use --links-file. Use --ui for the browser interface."
        )
        parser.print_help()
        return 1

    # --- Permission gate
    if not permission_gate(sources, has_permission_flag=config.get("i_have_permission", False), interactive=True):
        return 1

    # --- Process each source
    batch_results: list[dict[str, Any]] = []
    top_n: int = config.get("clips", 5)
    min_dur: int = config.get("min", 15)
    max_dur: int = config.get("max", 45)
    model_name: str = config.get("model", "base")
    language: str = config.get("language", "auto")
    style: str = config.get("style", "blur")
    caption_style: str = config.get("captions", "bold")
    crf: int = int(config.get("crf", 20))
    ffmpeg_preset: str = config.get("preset_ffmpeg", config.get("preset", "medium"))
    audio_bitrate: str = config.get("audio_bitrate", "192k")
    scoring_weights: dict[str, float] = config.get("_scoring_weights", {})
    scene_threshold: float = float(config.get("_scene_change_threshold", 0.3))
    vad_filter: bool = bool(config.get("_vad_filter", True))
    word_timestamps: bool = bool(config.get("_word_timestamps", True))
    chunk_hours: float = float(config.get("_chunk_hours", 2.5))
    cache_transcripts: bool = bool(config.get("_cache_transcripts", True))
    hook_words: list[str] = config.get("hook_words", [])
    if config.get("hook_text"):
        hook_words = [config["hook_text"]] + hook_words
    dry_run: bool = config.get("dry_run", False)
    no_captions: bool = config.get("no_captions", False)
    mask_profanity: bool = config.get("mask_profanity", False)
    translate: bool = config.get("translate_to_english", False)
    keep_temp: bool = config.get("keep_temp", False)
    source_start: float | None = config.get("start")
    source_end: float | None = config.get("end")

    interrupted = False

    for source in sources:
        t_start_proc = time.time()
        source_result: dict[str, Any] = {"source": source["raw"], "ok": False, "clips": 0, "out_dir": "—"}
        try:
            # --- Resolve local path (download if URL)
            if source["kind"] in ("youtube", "kick", "url", "gdrive"):
                tmp_dl_dir = out_dir / "_downloads"
                tmp_dl_dir.mkdir(parents=True, exist_ok=True)
                local_path = _download_url(source, tmp_dl_dir, config)
                if local_path is None:
                    logger.error("Could not download: %s", source["raw"])
                    continue
            elif source["kind"] == "file":
                local_path = Path(source["resolved"])
            elif source["kind"] == "dir":
                # Expand directory to individual video files
                video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
                dir_path = Path(source["resolved"])
                video_files = [p for p in dir_path.iterdir() if p.suffix.lower() in video_exts]
                if not video_files:
                    logger.warning("No video files found in directory: %s", dir_path)
                    continue
                # Queue each file as a separate source (recursive single-file processing)
                for vf in sorted(video_files):
                    sources.append({"raw": str(vf), "kind": "file", "resolved": str(vf)})
                logger.info("Queued %d file(s) from directory: %s", len(video_files), dir_path)
                source_result["ok"] = True
                continue
            else:
                logger.warning("Unknown source kind '%s' for: %s", source["kind"], source["raw"])
                continue

            # --- Check max source hours
            if config.get("max_source_hours"):
                try:
                    info = probe_video(local_path)
                    dur_h = info.get("duration", 0) / 3600
                    if dur_h > config["max_source_hours"]:
                        logger.info(
                            "Skipping %s (%.2f h > --max-source-hours %.2f h)",
                            local_path.name, dur_h, config["max_source_hours"],
                        )
                        continue
                except Exception:
                    pass  # probe failure handled below

            # --- Source-specific output directory
            safe_name = _sanitize_name(local_path.stem)
            src_out = out_dir / safe_name
            src_out.mkdir(parents=True, exist_ok=True)
            source_result["out_dir"] = str(src_out)

            # --- Probe video
            try:
                video_info = probe_video(local_path)
            except Exception as exc:
                logger.error("probe_video failed for %s: %s", local_path, exc)
                continue

            video_duration: float = video_info.get("duration", 0.0)
            effective_start = source_start or 0.0
            effective_end = min(source_end or video_duration, video_duration)

            # --- Transcribe
            try:
                words = transcribe_video(
                    path=local_path,
                    model_name=model_name,
                    language=language,
                    translate=translate,
                    vad_filter=vad_filter,
                    word_timestamps=word_timestamps,
                    chunk_hours=chunk_hours,
                    cache=cache_transcripts,
                    out_dir=src_out,
                )
            except Exception as exc:
                logger.error("Transcription failed for %s: %s", local_path, exc)
                words = []

            # Filter words to effective range
            words = [w for w in words if effective_start <= w.get("start", 0) < effective_end]

            # --- Analysis
            try:
                scene_times = detect_scene_changes(local_path, scene_threshold)
            except Exception as exc:
                logger.warning("Scene detection failed: %s", exc)
                scene_times = []

            try:
                audio_energy = compute_audio_energy(local_path)
            except Exception as exc:
                logger.warning("Audio energy failed: %s", exc)
                audio_energy = []

            # --- Scoring
            try:
                clips = score_clips(
                    words=words,
                    audio_energy=audio_energy,
                    scene_changes=scene_times,
                    hook_words=hook_words,
                    min_dur=min_dur,
                    max_dur=max_dur,
                    top_n=top_n,
                    scoring_weights=scoring_weights,
                    video_duration=effective_end - effective_start,
                )
            except Exception as exc:
                logger.error("Scoring failed for %s: %s", local_path, exc)
                continue

            # Offset clips by effective_start
            for clip in clips:
                clip["start"] = clip.get("start", 0) + effective_start
                clip["end"] = clip.get("end", 0) + effective_start

            # --- Dry run
            if dry_run:
                _print_clip_table(clips, local_path.name)
                source_result["ok"] = True
                source_result["clips"] = len(clips)
                continue

            # --- Resume: skip already-rendered clips
            if config.get("resume"):
                clips = [
                    c for c in clips
                    if not (src_out / f"clip_{clips.index(c) + 1:02d}.mp4").exists()
                ]

            # --- Render each clip
            rendered_clips: list[dict[str, Any]] = []
            for idx, clip in enumerate(clips, 1):
                clip_stem = src_out / f"clip_{idx:02d}"
                clip_path = clip_stem.with_suffix(".mp4")

                clip_start = clip["start"]
                clip_end = clip["end"]

                # Build captions
                ass_file: Path | None = None
                if not no_captions and words:
                    try:
                        _, ass_file = build_captions(
                            words=words,
                            clip_start=clip_start,
                            clip_end=clip_end,
                            out_stem=clip_stem,
                            style=caption_style,
                            mask_profanity=mask_profanity,
                            translate=translate,
                        )
                    except Exception as exc:
                        logger.warning("Caption build failed for clip %d: %s", idx, exc)

                # Render
                try:
                    ok = render_clip(
                        source=local_path,
                        start=clip_start,
                        end=clip_end,
                        out_path=clip_path,
                        style=style,
                        crf=crf,
                        preset=ffmpeg_preset if ffmpeg_preset in ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow") else "medium",
                        audio_bitrate=audio_bitrate,
                        ass_path=ass_file,
                        hook_text=config.get("hook_text"),
                    )
                    if ok:
                        clip["output_file"] = str(clip_path)
                        rendered_clips.append(clip)
                        logger.info("Rendered clip %d/%d → %s", idx, len(clips), clip_path.name)
                    else:
                        logger.error("render_clip returned False for clip %d", idx)
                except Exception as exc:
                    logger.error("Render failed for clip %d: %s", idx, exc)

            # --- Write CSV and summary
            write_clips_csv(
                clips=rendered_clips,
                out_dir=src_out,
                source_url_or_path=source["raw"],
                words=words,
                hook_words=hook_words,
                preset=config.get("preset") or "general",
            )
            write_summary_md(
                source_name=local_path.stem,
                clips=rendered_clips,
                out_dir=src_out,
                config=config,
                source_url_or_path=source["raw"],
                video_duration=video_duration,
                processing_time=time.time() - t_start_proc,
                words=words,
                hook_words=hook_words,
                preset=config.get("preset") or "general",
            )
            _print_clip_table(rendered_clips, local_path.name)

            # --- Cleanup temp files
            if not keep_temp and source["kind"] in ("youtube", "kick", "url", "gdrive"):
                try:
                    local_path.unlink(missing_ok=True)
                except Exception:
                    pass

            source_result["ok"] = True
            source_result["clips"] = len(rendered_clips)

        except KeyboardInterrupt:
            from rich.console import Console
            Console().print("\n[bold yellow]Interrupted -- saving partial results...[/bold yellow]")
            interrupted = True
        except Exception as exc:
            logger.error("Unexpected error processing %s:\n%s", source["raw"], traceback.format_exc())
            source_result["error"] = str(exc)
        finally:
            batch_results.append(source_result)

        if interrupted:
            break

    _print_final_summary(batch_results)

    if interrupted:
        return 130  # conventional exit code for Ctrl+C
    failures = sum(1 for r in batch_results if not r["ok"])
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
