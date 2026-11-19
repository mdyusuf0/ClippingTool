"""
clipfinder/ui.py
================
GTA VI Clipping Studio — Minimalist & Premium Local Web Interface.

Designed with an obsidian/slate luxury aesthetic inspired by Rockstar Games & Apple design principles.
Autonomous short-form 9:16 extraction (TikTok, YouTube Shorts, Instagram Reels) with
word-by-word highlighted karaoke subtitles, audio loudness normalization (-14 LUFS),
and optional Gemini AI title enhancement.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

from clipfinder.cancellation import cancellation_token, CancellationError

# Ensure clipfinder package is importable
_PKG_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _PKG_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Assets Loader
# ---------------------------------------------------------------------------

def _load_asset_b64(filename: str) -> str:
    """Load an asset file from disk and return its base64 string."""
    search_dirs = [
        _ROOT_DIR / "assets",
        _PKG_DIR / "assets",
        Path("assets"),
        Path("clipfinder/assets"),
    ]
    for d in search_dirs:
        p = d / filename
        if p.exists():
            try:
                return base64.b64encode(p.read_bytes()).decode("utf-8")
            except CancellationError:
                raise
            except Exception:
                pass
    return ""


# ---------------------------------------------------------------------------
# Categories & Presets Definition
# ---------------------------------------------------------------------------

CATEGORY_MAP: dict[str, str] = {
    "Action & Shootouts (Combat, Wanted Levels, SWAT)": "action",
    "Vehicles & Chases (High-speed pursuits, escapes, drifts)": "chases",
    "Fails & Physics (Ragdoll glitches, NPC chaos, unscripted)": "funny",
    "Story & Dialogue (Lucia & Jason lore, cinematic cutscenes)": "serious",
    "Dramatic & Emotional (Character moments, downfalls, betrayal)": "sad",
    "Atmosphere & Scenery (Vice City sunsets, ocean drives, ambient)": "cinematic",
    "Stunts & Aerials (Ramp jumps, skydiving, precision maneuvers)": "stunts",
    "Clutch Gameplay (High-skill gunplay, tactical clutches)": "gaming",
}

DEFAULT_CATEGORY = "Action & Shootouts (Combat, Wanted Levels, SWAT)"

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_yaml_config() -> dict[str, Any]:
    """Load configuration from config.yaml if available."""
    cfg_paths = [
        _ROOT_DIR / "config.yaml",
        Path("config.yaml"),
        Path.cwd() / "config.yaml",
    ]
    for p in cfg_paths:
        if p.exists():
            try:
                import yaml  # type: ignore[import-untyped]
                with p.open("r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                    if isinstance(data, dict):
                        return data
            except Exception as exc:
                logger.warning("Failed loading %s: %s", p, exc)
    return {}


# ---------------------------------------------------------------------------
# Pre-rendered 9:16 Viral Reels Manifest & Resolvers
# ---------------------------------------------------------------------------

REELS_MANIFEST: list[dict[str, Any]] = [
    {
        "id": "reel_01",
        "title": "xQc Haunted Radio Demon Glitch",
        "filename": "GTA6_Glitch_xQc_RadioDemon_Reel.mp4",
        "thumb": "GTA6_Glitch_xQc_RadioDemon_Reel_thumb.jpg",
        "category": "Creator Glitches & Reactions",
        "hook": "Radio: 'No son! LOOK AWAY!' 💀",
        "audio": "Original xQc Voice + Radio Glitch + Vine Boom & Bruh SFX",
        "caption": "xQc found a cursed radio demon in GTA 6 💀 Bro was fighting for his life!",
        "tags": "#GTA6 #GTA6Glitch #xQc #GamingMemes #Shorts #TikTok",
    },
    {
        "id": "reel_02",
        "title": "Speed KFC & Keanu Reeves Glitch",
        "filename": "GTA6_Glitch_Speed_KFC_Keanu_Reel.mp4",
        "thumb": "GTA6_Glitch_Speed_KFC_Keanu_Reel_thumb.jpg",
        "category": "Creator Glitches & Reactions",
        "hook": "Speed: 'WAIT... THAT'S KFC?! NO! THAT'S KEANU REEVES!' 🍗",
        "audio": "Original Speed Voice + Vine Boom & Bruh SFX",
        "caption": "SPEED FOUND KEANU REEVES AND A KFC BUCKET IN GTA 6 😭 Rockstar explain this!",
        "tags": "#IShowSpeed #Speed #GTA6 #GTA6Memes #KeanuReeves #Shorts",
    },
    {
        "id": "reel_03",
        "title": "IShowSpeed Tokyo Girl Hype",
        "filename": "GTA6_TokyoGirl_Speed_Hype_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Speed_Hype_Reel_thumb.jpg",
        "category": "GTA 6 Memes & Hype",
        "hook": "SPEED'S REACTION TO GTA 6 IS PRICELESS 💀",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Tokyo Girl hits different with Speed's GTA 6 hype 🔥 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #IShowSpeed #GTA6Hype #ViralReel",
    },
    {
        "id": "reel_04",
        "title": "IShowSpeed Trailer & Lucia Lore",
        "filename": "GTA6_TokyoGirl_Speed_Story_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Speed_Story_Reel_thumb.jpg",
        "category": "Story, Dialogue & Reactions",
        "hook": "WHEN THE GTA 6 TRAILER HIT DIFFERENT 🔥",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Waiting for GTA 6 feels like an eternity 😭 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #IShowSpeed #Lucia #ViceCity",
    },
    {
        "id": "reel_05",
        "title": "CarryMinati Arrest & Lucia Reveal",
        "filename": "GTA6_TokyoGirl_Carry_Arrest_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Carry_Arrest_Reel_thumb.jpg",
        "category": "Action & Story",
        "hook": "CARRYMINATI CAN'T BELIEVE GTA 6 GRAPHICS 🤯",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Vice City police aren't playing around 🚔 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #CarryMinati #ViceCity #GamingReels",
    },
    {
        "id": "reel_06",
        "title": "CarryMinati Vice City Cruising",
        "filename": "GTA6_TokyoGirl_Carry_ViceCity_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Carry_ViceCity_Reel_thumb.jpg",
        "category": "Vehicles & Vice City Views",
        "hook": "VICE CITY AT NIGHT WITH CARRYMINATI 🌴",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Night drives through Vice City hit different 🌙 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #CarryMinati #ViceCityVibes #Reels",
    },
    {
        "id": "reel_07",
        "title": "Vice City Beach Sunset Cinematic",
        "filename": "GTA6_TokyoGirl_Landscape_Sunset_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Landscape_Sunset_Reel_thumb.jpg",
        "category": "Atmosphere & Scenery",
        "hook": "VICE CITY SUNSET IS PURE POETRY 🌅",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Some cities look like heaven from far away... 🌅 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #ViceCity #GTA6Cinematic #Aesthetic",
    },
    {
        "id": "reel_08",
        "title": "Jason & Lucia 'Trust' Relationship Edit",
        "filename": "GTA6_TokyoGirl_JasonLucia_Trust_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_JasonLucia_Trust_Reel_thumb.jpg",
        "category": "Jason & Lucia Relationship Edit",
        "hook": "THE ONLY WAY WE'RE GONNA GET THROUGH THIS... TRUST. ❤️",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Partners in crime. The only way we get through this is trust. ❤️ Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #JasonAndLucia #PartnersInCrime #StoryMode",
    },
    {
        "id": "reel_09",
        "title": "Lucia Prison Bad Luck Lore Edit",
        "filename": "GTA6_TokyoGirl_Lucia_Prison_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_Lucia_Prison_Reel_thumb.jpg",
        "category": "Dramatic & Emotional Lore",
        "hook": "BAD LUCK, I GUESS... LUCIA'S STORY BEGINS ⛓️",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "How did Lucia end up in prison? Bad luck, I guess... ⛓️ Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #Lucia #GTA6Lore #Leonida",
    },
    {
        "id": "reel_10",
        "title": "Vice City Ocean Drive Neon Nights",
        "filename": "GTA6_TokyoGirl_ViceCity_NeonNights_Reel.mp4",
        "thumb": "GTA6_TokyoGirl_ViceCity_NeonNights_Reel_thumb.jpg",
        "category": "Atmosphere & Scenery",
        "hook": "NEON NIGHTS IN LEONIDA 🌴🏎️",
        "audio": "Song: Tokyo Girl by @PassiveBand",
        "caption": "Welcome back to Vice City. 2026 can't come fast enough! 🌴 Song: Tokyo Girl by @PassiveBand",
        "tags": "#GTA6 #TokyoGirl #Leonida #ViceCityNights #GamingEdit",
    },
]


def resolve_reel_path(filename: str) -> str | None:
    """Find reel file on Desktop or inside repository rendered_reels."""
    candidates = [
        Path.home() / "Desktop" / filename,
        _ROOT_DIR / "rendered_reels" / filename,
        Path("rendered_reels") / filename,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c.resolve())
    return None


def resolve_thumb_path(thumb_name: str, vid_path: str | None = None) -> str | None:
    """Find thumbnail on Desktop or local repository, extracting from video if needed."""
    candidates = [
        Path.home() / "Desktop" / "thumbnails" / thumb_name,
        _ROOT_DIR / "rendered_reels" / "thumbnails" / thumb_name,
        Path("rendered_reels/thumbnails") / thumb_name,
        Path.home() / "Desktop" / thumb_name,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c.resolve())

    # Fallback: extract frame using ffmpeg
    if vid_path and Path(vid_path).exists():
        out_thumb = _ROOT_DIR / "rendered_reels" / "thumbnails" / thumb_name
        out_thumb.parent.mkdir(parents=True, exist_ok=True)
        try:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "2.0", "-i", str(vid_path), "-vframes", "1", "-q:v", "2", str(out_thumb)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if out_thumb.exists():
                return str(out_thumb.resolve())
        except Exception:
            pass
    return None


def load_default_rendered_state() -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    list[tuple[str, str]],
    list[list[Any]],
    str | None,
    str,
]:
    """Scan and load the 10 rendered reels with thumbnails, players, table and package."""
    vids: list[str | None] = []
    gallery_items: list[tuple[str, str]] = []
    df_rows: list[list[Any]] = []
    cards_parts: list[str] = [
        "### 🎬 Rendered 9:16 Vertical Video Outputs (10 Viral Reels Showcase)\n\n"
        "> **All reels are rendered in full-bleed 1080×1920 portrait format with burned-in subtitles & audio loudness mastering.**\n"
    ]

    for idx, item in enumerate(REELS_MANIFEST, 1):
        v_path = resolve_reel_path(item["filename"])
        t_path = resolve_thumb_path(item["thumb"], v_path)
        vids.append(v_path)

        display_thumb = t_path if t_path else (v_path or "")
        if display_thumb:
            gallery_items.append((display_thumb, f"Reel #{idx:02d}: {item['title']}"))

        df_rows.append([
            f"Reel #{idx:02d}",
            item["title"],
            item["category"],
            item["audio"],
            item["hook"],
            item["tags"],
        ])

        cards_parts.append(
            f"#### Reel #{idx:02d}: {item['title']} (1080×1920 Full Bleed)\n"
            f"- **Category:** `{item['category']}`\n"
            f"- **Audio / Soundtrack:** {item['audio']}\n"
            f"- **Hook / Punchline:** *{item['hook']}*\n"
            f"- **Ready-to-Post Caption:** `{item['caption']}`\n"
            f"- **Hashtags:** `{item['tags']}`\n"
            f"- **File Location:** `{v_path if v_path else 'Not yet found on Desktop or local'}`\n"
        )

    cards_md = "\n".join(cards_parts)

    # Check or create zip package
    zip_candidates = [
        _ROOT_DIR / "rendered_reels" / "GTA6_ALL_REELS_PACKAGE.zip",
        Path("rendered_reels/GTA6_ALL_REELS_PACKAGE.zip"),
    ]
    zip_res: str | None = None
    for z in zip_candidates:
        if z.exists():
            zip_res = str(z.resolve())
            break

    # If missing but reels exist, generate it
    if not zip_res:
        valid_vids = [p for p in vids if p and Path(p).exists()]
        if valid_vids:
            try:
                import zipfile
                out_zip = _ROOT_DIR / "rendered_reels" / "GTA6_ALL_REELS_PACKAGE.zip"
                out_zip.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for vp in valid_vids:
                        zf.write(vp, arcname=Path(vp).name)
                    for item in REELS_MANIFEST:
                        tp = resolve_thumb_path(item["thumb"])
                        if tp and Path(tp).exists():
                            zf.write(tp, arcname=f"thumbnails/{Path(tp).name}")
                if out_zip.exists():
                    zip_res = str(out_zip.resolve())
            except Exception as exc:
                logger.warning("Could not auto-generate zip: %s", exc)

    while len(vids) < 10:
        vids.append(None)

    return (
        vids[0], vids[1], vids[2], vids[3], vids[4],
        vids[5], vids[6], vids[7], vids[8], vids[9],
        gallery_items,
        df_rows,
        zip_res,
        cards_md,
    )

# ---------------------------------------------------------------------------
# Pipeline Execution
# ---------------------------------------------------------------------------

def _run_pipeline(
    urls_text: str,
    uploaded_files: list[Any] | None,
    category_label: str,
    has_permission: bool,
    n_clips: int,
    min_duration: float,
    max_duration: float,
    style: str,
    captions_preset: str,
    mask_profanity: bool,
    hook_text: str,
    model: str,
    language: str,
    gemini_api_key: str,
    live_duration: float = 2.0,
    live_from_start: bool = False,
    progress: Any = None,
) -> tuple[
    str | None,  # video 1
    str | None,  # video 2
    str | None,  # video 3
    str | None,  # video 4
    str | None,  # video 5
    list[tuple[str, str]],  # gallery
    list[list[Any]],  # dataframe rows
    str | None,  # zip file
    str,  # status
    str,  # markdown cards
]:
    """
    Execute the end-to-end GTA 6 Clipping pipeline.
    """
    cancellation_token.reset()
    try:
        from clipfinder.ingest import (
            classify_input,
            probe_video,
            permission_gate,
            download_source,
        )
        from clipfinder.score import (
            score_clips,
            detect_scene_changes,
            compute_audio_energy,
        )
        from clipfinder.transcribe import transcribe_video
        from clipfinder.captions import (
            group_words,
            build_srt_file,
            build_ass_file,
        )
        from clipfinder.render import render_clip
        from clipfinder.output import (
            write_clips_csv,
            write_summary_md,
            generate_local_metadata,
            try_gemini_enhance,
            create_zip,
        )
    except ImportError as exc:
        err = f"Pipeline import error: {exc}"
        logger.error(err)
        return (*[None] * 10, [], [], None, f"Error: {err}", "")

    try:
        t_start_total = time.time()
        cat_key = CATEGORY_MAP.get(category_label, "general")
        yaml_cfg = _load_yaml_config()
        preset_cfg = yaml_cfg.get("presets", {}).get(cat_key, {})
        default_scoring_weights = yaml_cfg.get("scoring_weights", {
            "loudness": 0.25,
            "speech_rate": 0.20,
            "hook_word": 0.20,
            "punctuation": 0.15,
            "scene_change": 0.20,
        })
        scoring_weights = preset_cfg.get("scoring_weights", default_scoring_weights)
        hook_words = preset_cfg.get("hook_words", [
            "insane", "no way", "gta 6", "vice city", "lucia", "jason", "cops", "fast", "wasted"
        ])
    
        # ---- 1. Ingest inputs ----
        input_lines: list[str] = [
            line.strip() for line in (urls_text or "").splitlines() if line.strip()
        ]
        if uploaded_files:
            for f in uploaded_files:
                fp = f if isinstance(f, str) else getattr(f, "name", "")
                if fp and fp.strip():
                    input_lines.append(fp.strip())
    
        if not input_lines:
            return (
                *[None] * 10, [], [], None,
                "Notice: No inputs provided. Please enter a video URL or upload a file.",
                "",
            )
    
        # ---- 2. Permission Gate ----
        if progress:
            progress(0.05, desc="Verifying source permission...")
    
        allowed = permission_gate(input_lines, has_permission_flag=has_permission, interactive=False)
        if not allowed:
            return (
                *[None] * 10, [], [], None,
                "Permission required: External URL download requires rights confirmation. "
                "Please check the permission confirmation box to proceed.",
                "",
            )
    
        # ---- 3. Create temp workspace ----
        out_dir = Path(tempfile.mkdtemp(prefix=f"gta6_{cat_key}_"))
        downloads_dir = out_dir / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Output working directory: %s", out_dir)
    
        # ---- 4. Resolve / Download video sources ----
        local_videos: list[tuple[Path, str]] = []  # (local_path, source_url_or_raw)
        total_inputs = len(input_lines)
    
        for i, raw_item in enumerate(input_lines):
            cancellation_token.check_canceled()
            if progress:
                progress(0.1 + 0.25 * (i / max(total_inputs, 1)), desc=f"Connecting source {i+1}/{total_inputs}...")
            kind, resolved = classify_input(raw_item)
            if kind == "file":
                p = Path(resolved)
                if p.exists():
                    local_videos.append((p, raw_item))
                else:
                    logger.warning("Local file not found: %s", resolved)
            elif kind in ("youtube", "kick", "url", "gdrive"):
                if progress:
                    progress(0.15 + 0.25 * (i / max(total_inputs, 1)), desc=f"Ingesting {kind.upper()} media...")
                dl = download_source(
                    raw_item,
                    downloads_dir,
                    config={
                        "live_duration": live_duration,
                        "live_from_start": live_from_start,
                    },
                )
                if dl and dl.exists():
                    local_videos.append((dl, raw_item))
                else:
                    logger.error("Failed downloading source: %s", raw_item)
    
        if not local_videos:
            return (
                *[None] * 10, [], [], None,
                "Error: Could not resolve or download any video from the provided input(s). "
                "Please verify the URL or file path.",
                "",
            )
    
        # ---- 5. Process Videos & Extract Viral Moments ----
        rendered_clips_paths: list[str] = []
        all_clips_data: list[dict[str, Any]] = []
    
        for vid_idx, (vid_path, raw_source) in enumerate(local_videos):
            cancellation_token.check_canceled()
            if progress:
                progress(
                    0.35 + 0.45 * (vid_idx / max(len(local_videos), 1)),
                    desc=f"Analyzing {vid_path.name} for {cat_key} moments...",
                )
            try:
                # Probe
                info = probe_video(vid_path)
                duration = float(info.get("duration", 0.0))
                if duration <= 0:
                    logger.warning("Video duration <= 0: %s", vid_path)
                    continue
    
                # Transcribe (offline Whisper)
                if progress:
                    progress(0.42, desc="Transcribing audio with Whisper AI (local)...")
                try:
                    words = transcribe_video(
                        path=vid_path,
                        model_name=model,
                        language=language,
                        vad_filter=True,
                        word_timestamps=True,
                        out_dir=out_dir,
                    )
                except CancellationError:
                    raise
                except Exception as exc:
                    logger.warning("Transcription notice: %s; using audio & scene energy fallback.", exc)
                    words = []
    
                # Visual cuts and Audio spikes
                if progress:
                    progress(0.55, desc="Analyzing visual cuts and volume spikes...")
                try:
                    scene_cuts = detect_scene_changes(vid_path, threshold=0.3)
                except CancellationError:
                    raise
                except Exception:
                    scene_cuts = []

                try:
                    audio_energy = compute_audio_energy(vid_path)
                except CancellationError:
                    raise
                except Exception:
                    audio_energy = []
    
                # Scoring
                if progress:
                    progress(0.65, desc=f"Evaluating top {n_clips} {cat_key} windows...")
                clips = score_clips(
                    words=words,
                    audio_energy=audio_energy,
                    scene_changes=scene_cuts,
                    hook_words=hook_words,
                    min_dur=int(min_duration),
                    max_dur=int(max_duration),
                    top_n=n_clips,
                    scoring_weights=scoring_weights,
                    video_duration=duration,
                )
    
                if not clips:
                    logger.warning("No candidate clips found for %s", vid_path.name)
                    continue
    
                # Render each clip
                for c_idx, clip in enumerate(clips, 1):
                    cancellation_token.check_canceled()
                    clip_start = float(clip.get("start", 0.0))
                    clip_end = float(clip.get("end", 0.0))
                    clip_dur = clip_end - clip_start
                    if clip_dur <= 0:
                        continue
    
                    if progress:
                        progress(
                            0.70 + 0.20 * (c_idx / max(len(clips), 1)),
                            desc=f"Rendering 9:16 vertical Reel {c_idx}/{len(clips)} (1080x1920)...",
                        )
    
                    clip_stem = f"gta6_{cat_key}_clip_{c_idx:02d}"
                    clip_mp4 = out_dir / f"{clip_stem}.mp4"
                    clip_srt = out_dir / f"{clip_stem}.srt"
                    clip_ass = out_dir / f"{clip_stem}.ass"
    
                    # Subtitles
                    ass_path_to_burn: Path | None = None
                    clip_words = [
                        {**w, "start": w["start"] - clip_start, "end": w["end"] - clip_start}
                        for w in words
                        if clip_start <= w.get("start", 0.0) < clip_end
                    ]
    
                    if captions_preset != "none" and clip_words:
                        try:
                            groups = group_words(clip_words, max_per_group=5)
                            build_srt_file(groups, clip_srt, mask_profanity=mask_profanity)
                            build_ass_file(
                                groups=groups,
                                out_path=clip_ass,
                                style=captions_preset,
                                duration=clip_dur,
                                mask_profanity=mask_profanity,
                            )
                            ass_path_to_burn = clip_ass
                        except CancellationError:
                            raise
                        except Exception as exc:
                            logger.warning("Caption build notice for clip %d: %s", c_idx, exc)
    
                    # Render video (1080x1920 portrait, loudnorm -14 LUFS, AAC 192k)
                    effective_hook = hook_text.strip() if hook_text and hook_text.strip() else None
                    success = render_clip(
                        source=vid_path,
                        start=clip_start,
                        end=clip_end,
                        out_path=clip_mp4,
                        style=style,
                        crf=20,
                        preset="veryfast",
                        audio_bitrate="192k",
                        ass_path=ass_path_to_burn,
                        hook_text=effective_hook,
                    )
    
                    if success and clip_mp4.exists():
                        rendered_clips_paths.append(str(clip_mp4))
    
                        # Metadata
                        snippet = " ".join(w.get("text", "") for w in clip_words).strip()
                        if not snippet:
                            snippet = f"GTA 6 {cat_key} gameplay clip in Vice City"
    
                        meta = generate_local_metadata(
                            transcript_snippet=snippet,
                            hook_words=hook_words,
                            score=float(clip.get("score", 0.0)),
                            preset=cat_key,
                        )
    
                        clip_dict: dict[str, Any] = {
                            "filename": clip_mp4.name,
                            "source_url_or_path": raw_source,
                            "start": f"{clip_start:.2f}",
                            "end": f"{clip_end:.2f}",
                            "duration": f"{clip_dur:.2f}",
                            "score": f"{float(clip.get('score', 0.0)):.4f}",
                            "transcript_snippet": snippet[:200],
                            "suggested_title": meta.get("suggested_title", f"GTA 6 {cat_key.title()} Clip"),
                            "suggested_description": meta.get("suggested_description", ""),
                            "suggested_hashtags": meta.get("suggested_hashtags", "#GTA6 #ViceCity #shorts"),
                        }
                        all_clips_data.append(clip_dict)
    
            except CancellationError:
                raise
            except Exception:
                logger.error("Error processing %s:\n%s", vid_path, traceback.format_exc())
    
        if not rendered_clips_paths:
            return (
                *[None] * 10, [], [], None,
                "Pipeline completed but no clips could be produced. Please check video length and audio.",
                "",
            )
    
        # ---- 6. Optional Gemini AI Enhancement ----
        api_key_to_use = gemini_api_key.strip() if gemini_api_key and gemini_api_key.strip() else None
        if progress:
            progress(0.92, desc="Polishing metadata and viral tags...")
        all_clips_data = try_gemini_enhance(
            all_clips_data,
            source_context=f"Grand Theft Auto VI {cat_key} moment in Vice City",
            api_key=api_key_to_use,
        )
    
        # ---- 7. Write CSV, Summary MD, and ZIP ----
        if progress:
            progress(0.96, desc="Finalizing exports and package...")
    
        csv_path = out_dir / "clips.csv"
        md_path = out_dir / "summary.md"
        zip_path = out_dir / f"GTA6_{cat_key.upper()}_REELS.zip"
    
        write_clips_csv(all_clips_data, csv_path)
        total_clip_sec = sum(float(c.get("duration", 0)) for c in all_clips_data)
        total_proc_time = time.time() - t_start_total
    
        write_summary_md(
            source_name=Path(local_videos[0][0]).stem,
            source_url=local_videos[0][1],
            clips_data=all_clips_data,
            output_path=md_path,
            total_duration=total_clip_sec,
            processing_time=total_proc_time,
        )
        create_zip(out_dir, zip_path)
    
        # ---- 8. Prepare Return Values ----
        v_slots: list[str | None] = [
            rendered_clips_paths[i] if i < len(rendered_clips_paths) else None
            for i in range(10)
        ]
    
        # Gallery items
        gallery_items = [(p, f"Reel #{i+1:02d} — {cat_key.upper()}") for i, p in enumerate(rendered_clips_paths)]
    
        # Dataframe rows
        df_rows: list[list[Any]] = [
            [
                c.get("filename", ""),
                f"{float(c.get('start', 0)):.1f}s",
                f"{float(c.get('end', 0)):.1f}s",
                f"{float(c.get('duration', 0)):.1f}s",
                f"{float(c.get('score', 0)):.3f}",
                c.get("suggested_title", ""),
                c.get("suggested_hashtags", ""),
            ]
            for c in all_clips_data
        ]
    
        # Formatted Markdown Cards
        cards_md_parts: list[str] = [
            f"### Extracted Reels ({len(rendered_clips_paths)} Clips • Category: {cat_key.upper()})\n"
        ]
        for idx, c in enumerate(all_clips_data, 1):
            cards_md_parts.append(
                f"#### Reel #{idx:02d}: `{c.get('filename')}` ({c.get('duration')}s • Engagement: {c.get('score')})\n"
                f"- **Title**: {c.get('suggested_title')}\n"
                f"- **Description**: {c.get('suggested_description')}\n"
                f"- **Hashtags**: `{c.get('suggested_hashtags')}`\n"
            )
        cards_md = "\n".join(cards_md_parts)
    
        status_msg = (
            f"Completed: Extracted {len(rendered_clips_paths)} vertical reel(s) in {total_proc_time:.1f}s. "
            f"Package saved to {zip_path.name}."
        )
    
        if progress:
            progress(1.0, desc="Finished")
    
        zip_res = str(zip_path) if zip_path.exists() else None
        return v_slots[0], v_slots[1], v_slots[2], v_slots[3], v_slots[4], v_slots[5], v_slots[6], v_slots[7], v_slots[8], v_slots[9], gallery_items, df_rows, zip_res, status_msg, cards_md
    except CancellationError:
        logger.info("Pipeline was cancelled by user.")
        return (
            *[None] * 10, [], [], None,
            "Generation cancelled by user. Background tasks stopped.",
            "",
        )

# ---------------------------------------------------------------------------
# Minimalist Luxury CSS
# ---------------------------------------------------------------------------

PREMIUM_MINIMAL_CSS = """
/* Luxury Slate / Obsidian Minimalism */
:root {
    --bg-main: #0a0c10;
    --bg-card: #11141a;
    --bg-card-sub: #161922;
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-hover: rgba(255, 255, 255, 0.18);
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent: #f43f5e;
}

body, .gradio-container {
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Studio Header Bar */
.studio-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(17, 20, 26, 0.85);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 18px 24px;
    margin-bottom: 24px;
}

.brand-wrapper {
    display: flex;
    align-items: center;
    gap: 18px;
}

.brand-logo-img {
    height: 48px;
    width: auto;
    object-fit: contain;
    filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.6));
}

.brand-text-block {
    display: flex;
    flex-direction: column;
}

.brand-title-line {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
}

.brand-pill-tag {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: #fb7185;
    padding: 2px 8px;
    border-radius: 6px;
}

.brand-desc-line {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 3px;
    letter-spacing: -0.01em;
}

.status-cluster {
    display: flex;
    align-items: center;
    gap: 10px;
}

.spec-badge {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    background: #171b23;
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 6px 12px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.live-indicator-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
}

/* Minimal Card Surfaces */
.surface-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    padding: 20px !important;
}

.section-label {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--text-secondary) !important;
    margin-bottom: 12px !important;
}

/* Form Inputs */
input, textarea, select {
    background-color: var(--bg-card-sub) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-size: 0.9rem !important;
}

input:focus, textarea:focus, select:focus {
    border-color: rgba(255, 255, 255, 0.25) !important;
    box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.05) !important;
}

/* Tactile Primary Action Button */
.btn-primary-action {
    background: linear-gradient(180deg, #ffffff 0%, #e2e8f0 100%) !important;
    color: #0b0d11 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: -0.01em !important;
    border: 1px solid rgba(255, 255, 255, 0.5) !important;
    border-radius: 8px !important;
    padding: 13px 24px !important;
    cursor: pointer !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.8) !important;
    transition: all 0.15s ease-in-out !important;
}

.btn-primary-action:hover {
    background: #f8fafc !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

.btn-primary-action:active {
    transform: translateY(0) !important;
}

/* Minimalist Cancel / Stop Action Button */
.btn-cancel-action {
    background: #181114 !important;
    color: #f87171 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: -0.01em !important;
    border: 1px solid rgba(239, 68, 68, 0.35) !important;
    border-radius: 8px !important;
    padding: 13px 20px !important;
    cursor: pointer !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4) !important;
    transition: all 0.15s ease-in-out !important;
}

.btn-cancel-action:hover {
    background: #261217 !important;
    border-color: rgba(239, 68, 68, 0.6) !important;
    color: #fca5a5 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15) !important;
}

.btn-cancel-action:active {
    transform: translateY(0) !important;
}

/* Secondary Action Button */
.btn-secondary-action {
    background: #171b23 !important;
    color: #e2e8f0 !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
}

.btn-secondary-action:hover {
    background: #1e242f !important;
    border-color: rgba(255, 255, 255, 0.25) !important;
    color: #ffffff !important;
}

/* Terminal Log View */
.terminal-output textarea {
    font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace !important;
    font-size: 0.82rem !important;
    background-color: #0c0e13 !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    color: #94a3b8 !important;
}

/* Video Frame Restraint */
video {
    border-radius: 8px !important;
    border: 1px solid var(--border-subtle) !important;
    background: #000000 !important;
}
"""

# ---------------------------------------------------------------------------
# Public launch_ui
# ---------------------------------------------------------------------------

def launch_ui(default_config: dict | None = None) -> None:
    """
    Launch the GTA VI Clipping Studio with a minimalist luxury UI.
    Runs locally on http://127.0.0.1:7860.
    """
    try:
        import gradio as gr  # type: ignore[import-untyped]
    except ImportError:
        raise RuntimeError("Gradio is not installed. Run `pip install gradio`.")

    cfg: dict = default_config or {}
    default_n_clips = int(cfg.get("clips", cfg.get("n_clips", 4)))
    default_min = float(cfg.get("min", cfg.get("min_duration", 15.0)))
    default_max = float(cfg.get("max", cfg.get("max_duration", 35.0)))
    default_style = str(cfg.get("style", "blur"))
    default_captions = str(cfg.get("captions", cfg.get("captions_preset", "vice_city")))
    default_model = str(cfg.get("model", "base"))
    default_lang = str(cfg.get("lang", cfg.get("language", "auto")))

    # Prepare base64 images
    logo_b64 = _load_asset_b64("gta6_logo.svg")
    cover_b64 = _load_asset_b64("gta6_cover.png")

    (
        init_v1, init_v2, init_v3, init_v4, init_v5,
        init_v6, init_v7, init_v8, init_v9, init_v10,
        init_gallery, init_df, init_zip, init_cards,
    ) = load_default_rendered_state()

    with gr.Blocks(title="Grand Theft Auto VI — Clipping Studio") as demo:
        # ---- Minimalist Studio Header ----
        header_html = f"""
        <div class="studio-navbar">
            <div class="brand-wrapper">
                {"<img class='brand-logo-img' src='data:image/svg+xml;base64," + logo_b64 + "' alt='GTA VI Logo' />" if logo_b64 else ""}
                <div class="brand-text-block">
                    <div class="brand-title-line">
                        GTA VI Clipping Studio
                        <span class="brand-pill-tag">Local Studio</span>
                    </div>
                    <div class="brand-desc-line">
                        Automated 9:16 short-form extraction & karaoke reel generator for Vice City gameplay.
                    </div>
                </div>
            </div>
            <div class="status-cluster">
                <span class="spec-badge"><span class="live-indicator-dot"></span> Engine Online</span>
                <span class="spec-badge">1080×1920 30FPS</span>
                <span class="spec-badge">-14 LUFS Audio</span>
                <span class="spec-badge">Whisper Local</span>
            </div>
        </div>
        """
        gr.HTML(header_html)

        with gr.Tabs() as tabs:
            # ------------------------------------------------------------------
            # Tab 1: Studio Workbench
            # ------------------------------------------------------------------
            with gr.Tab("Studio Workbench"):
                with gr.Row():
                    # Left column: Ingestion
                    with gr.Column(scale=5, elem_classes=["surface-card"]):
                        gr.Markdown("<div class='section-label'>1. Source Media</div>")

                        category_dd = gr.Dropdown(
                            label="Moment Preset",
                            choices=list(CATEGORY_MAP.keys()),
                            value=DEFAULT_CATEGORY,
                            interactive=True,
                            info="Tunes speech recognition vocabulary, audio energy weights, and scene detection.",
                        )

                        url_input = gr.Textbox(
                            label="Source URL or Local Path",
                            placeholder="https://www.youtube.com/watch?v=... or https://youtube.com/live/... or Kick stream",
                            lines=2,
                        )

                        file_upload = gr.File(
                            label="Upload Local Video Files (.mp4, .mkv, .mov)",
                            file_count="multiple",
                            file_types=["video", ".mp4", ".mkv", ".mov", ".avi", ".webm"],
                        )

                        permission_checkbox = gr.Checkbox(
                            label="I confirm I have permission or own the rights to clip this media content",
                            value=True,
                        )

                        with gr.Accordion("Live Stream Capture Options (YouTube Live / Kick)", open=False):
                            live_dur_slider = gr.Slider(
                                label="Live Capture Duration (minutes)",
                                minimum=0.5,
                                maximum=15.0,
                                step=0.5,
                                value=2.0,
                                info="Extracts the latest N minutes of broadcast (1.5–2.0 min recommended for ultra-fast processing).",
                            )
                            live_from_start_cb = gr.Checkbox(
                                label="Capture from Stream Start (YouTube DVR)",
                                value=False,
                                info="Clips from the beginning of broadcast if DVR rewind is supported.",
                            )

                    # Right column: Reframe & Settings
                    with gr.Column(scale=4, elem_classes=["surface-card"]):
                        gr.Markdown("<div class='section-label'>2. Extraction & Reframe</div>")

                        with gr.Row():
                            n_clips_slider = gr.Slider(
                                label="Clips Count",
                                minimum=1,
                                maximum=10,
                                step=1,
                                value=default_n_clips,
                            )

                        with gr.Row():
                            min_dur_slider = gr.Slider(
                                label="Min Duration (s)",
                                minimum=10.0,
                                maximum=60.0,
                                step=5.0,
                                value=default_min,
                            )
                            max_dur_slider = gr.Slider(
                                label="Max Duration (s)",
                                minimum=15.0,
                                maximum=90.0,
                                step=5.0,
                                value=default_max,
                            )

                        with gr.Row():
                            style_dropdown = gr.Dropdown(
                                label="9:16 Vertical Framing",
                                choices=["blur", "crop", "facecrop"],
                                value=default_style,
                                info="blur: centered widescreen over blurred backdrop (recommended).",
                            )
                            captions_dropdown = gr.Dropdown(
                                label="Karaoke Captions Style",
                                choices=["vice_city", "pop", "bold", "minimal", "none"],
                                value=default_captions if default_captions in ("vice_city", "pop", "bold", "minimal", "none") else "vice_city",
                                info="vice_city: neon pink active word highlight.",
                            )

                        mask_profanity_cb = gr.Checkbox(
                            label="Mask profanity in captions (e.g. f***)",
                            value=True,
                        )

                        hook_text_box = gr.Textbox(
                            label="Intro Overlay Text (First 2s)",
                            placeholder="e.g. VICE CITY 2026 (optional)",
                            max_lines=1,
                        )

                        with gr.Accordion("Advanced Local AI Configuration", open=False):
                            model_dropdown = gr.Dropdown(
                                label="Whisper Speech Recognition Model",
                                choices=["tiny", "base", "small", "medium"],
                                value=default_model,
                            )
                            language_box = gr.Textbox(
                                label="Speech Language ('auto' for auto-detection)",
                                value=default_lang,
                                max_lines=1,
                            )
                            gemini_key_box = gr.Textbox(
                                label="Gemini API Key (Optional)",
                                placeholder="Leave empty for local offline generation",
                                type="password",
                                max_lines=1,
                            )

                # Action Buttons (Generate + Cancel Midway)
                with gr.Row():
                    generate_btn = gr.Button(
                        "Generate Vertical Reels",
                        elem_classes=["btn-primary-action"],
                        scale=3,
                        size="lg",
                    )
                    cancel_btn = gr.Button(
                        "Cancel Generation",
                        elem_classes=["btn-cancel-action"],
                        scale=1,
                        size="lg",
                    )

                status_box = gr.Textbox(
                    label="Studio Process Log",
                    interactive=False,
                    lines=3,
                    elem_classes=["terminal-output"],
                    placeholder="System ready. Select input source and parameters above.",
                )

            # ------------------------------------------------------------------
            # Tab 2: Rendered Reels & Exports
            # ------------------------------------------------------------------
            with gr.Tab("Rendered Reels & Exports"):
                with gr.Row():
                    gr.Markdown(
                        "<div class='section-label'>Rendered 9:16 Vertical Video Output (Desktop & Local Exports)</div>"
                    )
                    refresh_reels_btn = gr.Button(
                        "🔄 Rescan Desktop / Local Reels",
                        size="sm",
                        elem_classes=["btn-secondary-action"],
                    )

                # Video Players Grid (Reels 1 to 10)
                with gr.Row():
                    player_1 = gr.Video(value=init_v1, label="Reel 1: xQc Radio Glitch (9:16)", interactive=False, height=440)
                    player_2 = gr.Video(value=init_v2, label="Reel 2: Speed KFC & Keanu (9:16)", interactive=False, height=440)
                    player_3 = gr.Video(value=init_v3, label="Reel 3: Speed Tokyo Girl Hype (9:16)", interactive=False, height=440)

                with gr.Row():
                    player_4 = gr.Video(value=init_v4, label="Reel 4: Speed Trailer Lore (9:16)", interactive=False, height=440)
                    player_5 = gr.Video(value=init_v5, label="Reel 5: CarryMinati Arrest (9:16)", interactive=False, height=440)
                    player_6 = gr.Video(value=init_v6, label="Reel 6: CarryMinati Cruising (9:16)", interactive=False, height=440)

                with gr.Row():
                    player_7 = gr.Video(value=init_v7, label="Reel 7: Vice City Sunset (9:16)", interactive=False, height=440)
                    player_8 = gr.Video(value=init_v8, label="Reel 8: Jason & Lucia Trust (9:16)", interactive=False, height=440)
                    player_9 = gr.Video(value=init_v9, label="Reel 9: Lucia Prison Lore (9:16)", interactive=False, height=440)

                with gr.Row():
                    player_10 = gr.Video(value=init_v10, label="Reel 10: Neon Ocean Drive Drift (9:16)", interactive=False, height=440)

                gr.Markdown("<div class='section-label'>Complete Archive Download</div>")
                zip_file_output = gr.File(
                    value=init_zip,
                    label="Download Complete Package (.ZIP with 10 MP4 Clips, Thumbnails & Captions)",
                )

                cards_markdown = gr.Markdown(
                    value=init_cards,
                    label="Clip Metadata & Suggested Copy",
                )

                with gr.Accordion("Full Extraction Analytics & Moments Gallery", open=True):
                    clips_gallery = gr.Gallery(
                        value=init_gallery,
                        label="Moments & Thumbnails Gallery (Click to Inspect)",
                        columns=5,
                        height="auto",
                        object_fit="contain",
                    )
                    clips_table = gr.Dataframe(
                        value=init_df,
                        headers=[
                            "Reel", "Title", "Category", "Audio / Soundtrack", "Hook", "Hashtags",
                        ],
                        interactive=False,
                        wrap=True,
                    )

                refresh_reels_btn.click(
                    fn=load_default_rendered_state,
                    inputs=None,
                    outputs=[
                        player_1, player_2, player_3, player_4, player_5,
                        player_6, player_7, player_8, player_9, player_10,
                        clips_gallery, clips_table, zip_file_output, cards_markdown,
                    ],
                )

        # Wire Submit Callback
        def on_generate(
            urls_text: str,
            uploaded_files: list[Any] | None,
            category_label: str,
            has_permission: bool,
            n_clips: int,
            min_duration: float,
            max_duration: float,
            style: str,
            captions_preset: str,
            mask_profanity: bool,
            hook_text: str,
            model: str,
            language: str,
            gemini_api_key: str,
            live_duration: float,
            live_from_start: bool,
            progress: gr.Progress = gr.Progress(track_tqdm=True),
        ):
            return _run_pipeline(
                urls_text=urls_text,
                uploaded_files=uploaded_files,
                category_label=category_label,
                has_permission=has_permission,
                n_clips=n_clips,
                min_duration=min_duration,
                max_duration=max_duration,
                style=style,
                captions_preset=captions_preset,
                mask_profanity=mask_profanity,
                hook_text=hook_text,
                model=model,
                language=language,
                gemini_api_key=gemini_api_key,
                live_duration=live_duration,
                live_from_start=live_from_start,
                progress=progress,
            )

        def on_cancel() -> str:
            cancellation_token.cancel()
            return "Cancellation requested: Stopping active ffmpeg, Whisper, and download subprocesses..."

        generation_event = generate_btn.click(
            fn=on_generate,
            inputs=[
                url_input,
                file_upload,
                category_dd,
                permission_checkbox,
                n_clips_slider,
                min_dur_slider,
                max_dur_slider,
                style_dropdown,
                captions_dropdown,
                mask_profanity_cb,
                hook_text_box,
                model_dropdown,
                language_box,
                gemini_key_box,
                live_dur_slider,
                live_from_start_cb,
            ],
            outputs=[
                player_1,
                player_2,
                player_3,
                player_4,
                player_5,
                player_6,
                player_7,
                player_8,
                player_9,
                player_10,
                clips_gallery,
                clips_table,
                zip_file_output,
                status_box,
                cards_markdown,
            ],
        )

        cancel_btn.click(
            fn=on_cancel,
            inputs=None,
            outputs=[status_box],
            cancels=[generation_event],
        )

    # Launch server with luxury styling
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        css=PREMIUM_MINIMAL_CSS,
    )


if __name__ == "__main__":
    launch_ui()
