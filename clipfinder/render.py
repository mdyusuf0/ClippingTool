"""ClipFinder — render: ffmpeg-based clip extraction and reframing."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from clipfinder.cancellation import cancellation_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style filter builders
# ---------------------------------------------------------------------------

_TARGET_W = 1080
_TARGET_H = 1920  # 9:16 portrait


def _build_blur_filter(src_w: int, src_h: int) -> str:
    """
    Vertical reframe — blur:
      • Fast two-stage bokeh: downscale background before boxblur for 10x render speedup.
      • Blurred + scaled background fills 1080×1920.
      • Original video scaled to fit width, centred on top.
    """
    return (
        f"[0:v]scale=270:480:force_original_aspect_ratio=increase,"
        f"crop=270:480,boxblur=8:1,scale={_TARGET_W}:{_TARGET_H}[bg];"
        f"[0:v]scale={_TARGET_W}:-2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )


def _build_crop_filter(src_w: int, src_h: int) -> str:
    """
    Vertical reframe — crop:
      Centre-crop the original to 9:16 then scale to 1080×1920.
    """
    crop_w = min(src_w, int(src_h * _TARGET_W / _TARGET_H))
    crop_h = min(src_h, int(src_w * _TARGET_H / _TARGET_W))
    return (
        f"[0:v]crop={crop_w}:{crop_h}:"
        f"(iw-{crop_w})/2:(ih-{crop_h})/2,"
        f"scale={_TARGET_W}:{_TARGET_H}[v]"
    )


def _build_facecrop_filter(src_w: int, src_h: int, face_x: int | None = None) -> str:
    """
    Vertical reframe — facecrop:
      Crops around the detected face center X if available, otherwise falls back to centre-crop.
    """
    crop_w = min(src_w, int(src_h * _TARGET_W / _TARGET_H))
    crop_h = min(src_h, int(src_w * _TARGET_H / _TARGET_W))
    if face_x is not None:
        crop_x = max(0, min(int(face_x - crop_w / 2), src_w - crop_w))
    else:
        crop_x = (src_w - crop_w) // 2
    crop_y = (src_h - crop_h) // 2
    return (
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={_TARGET_W}:{_TARGET_H}[v]"
    )


def facecrop_offset(source: Path, sample_interval: float = 5.0) -> int | None:
    """
    Sample frames every *sample_interval* seconds using OpenCV Haar cascade,
    and return the median detected face center X coordinate, or None if no face found.
    """
    try:
        import cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            return None

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(fps * sample_interval))
        centers_x: list[int] = []
        frame_idx = 0

        while frame_idx < 1000:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
                for (x, y, w, h) in faces:
                    centers_x.append(int(x + w / 2))
            frame_idx += 1
        cap.release()

        if centers_x:
            import statistics
            return int(statistics.median(centers_x))
    except Exception as exc:
        logger.debug("OpenCV face detection skipped: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Public render function
# ---------------------------------------------------------------------------

def render_clip(
    source: Path,
    start: float,
    end: float,
    out_path: Path,
    style: str = "blur",
    crf: int = 20,
    preset: str = "veryfast",
    audio_bitrate: str = "192k",
    ass_path: Path | None = None,
    hook_text: str | None = None,
) -> bool:
    """
    Render a single clip from *source* between *start* and *end* seconds.

    Parameters
    ----------
    source:
        Input video file path.
    start, end:
        Clip time range in seconds.
    out_path:
        Destination ``.mp4`` file.
    style:
        ``blur`` | ``crop`` | ``facecrop``.
    crf:
        H.264 Constant Rate Factor (lower = higher quality, 18–28 typical).
    preset:
        ffmpeg x264 encoding preset (default: "veryfast").
    audio_bitrate:
        AAC audio bitrate string, e.g. ``"192k"``.
    ass_path:
        Optional ``.ass`` subtitle file to burn into the video.
    hook_text:
        Optional short text overlay in the first 2 seconds.

    Returns
    -------
    bool
        True on success, False on ffmpeg error.
    """
    cancellation_token.check_canceled()
    duration = end - start
    if duration <= 0:
        logger.error("Invalid clip range: start=%.2f end=%.2f", start, end)
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe source dimensions and audio
    src_w, src_h = _probe_dimensions(source)
    has_audio = _probe_has_audio(source)

    # Build video filter chain
    if style == "blur":
        vf = _build_blur_filter(src_w, src_h)
    elif style == "facecrop":
        face_x = facecrop_offset(source)
        vf = _build_facecrop_filter(src_w, src_h, face_x=face_x)
    else:  # crop
        vf = _build_crop_filter(src_w, src_h)

    # Optional hook text in first 2 seconds
    if hook_text:
        clean_hook = hook_text.replace("'", "").replace(":", "\\:").replace("%", "\\%")
        hook_filter = (
            f"drawtext=text='{clean_hook}':fontsize=80:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h/4):enable='between(t,0,2)':box=1:boxcolor=black@0.6:boxborderw=10"
        )
        vf = f"{vf};[v]{hook_filter}[v]"

    # Optionally append ASS burn-in filter
    if ass_path is not None and ass_path.exists():
        # Escape Windows backslashes for ffmpeg filter
        ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf = f"{vf};[v]ass='{ass_escaped}'[v]"

    cmd = [
        "ffmpeg",
        "-y",                           # overwrite
        "-nostdin",
        "-threads", "0",
        "-ss", str(start),              # seek BEFORE input for speed
        "-i", str(source),
        "-t", str(duration),
        "-filter_complex", vf,
        "-map", "[v]",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-movflags", "+faststart",
    ]

    # Audio handling: loudnorm (-14 LUFS) and short fade in/out if audio exists
    if has_audio:
        fade_out_start = max(0.0, duration - 0.3)
        af = (
            f"loudnorm=I=-14:TP=-1.5:LRA=11,"
            f"afade=t=in:ss=0:d=0.3,"
            f"afade=t=out:st={fade_out_start:.3f}:d=0.3"
        )
        cmd.extend([
            "-map", "0:a:0",
            "-af", af,
            "-c:a", "aac",
            "-b:a", audio_bitrate,
        ])
    else:
        cmd.extend(["-an"])

    cmd.append(str(out_path))

    logger.debug("ffmpeg cmd: %s", " ".join(cmd))
    try:
        result = cancellation_token.run_command(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        logger.error("ffmpeg not found — install ffmpeg.")
        return False

    if result.returncode != 0:
        logger.error(
            "ffmpeg failed (exit %d) for %s:\n%s",
            result.returncode,
            out_path.name,
            result.stderr[-2000:],
        )
        return False

    if not out_path.exists() or out_path.stat().st_size == 0:
        logger.error("Output file missing or empty: %s", out_path)
        return False

    logger.info("Rendered: %s (%.1f s)", out_path.name, duration)
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _probe_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream, or (1920, 1080) on error."""
    import json

    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-print_format", "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        streams = data.get("streams", [{}])
        if streams:
            return int(streams[0].get("width", 1920)), int(streams[0].get("height", 1080))
    except Exception as exc:
        logger.warning("Could not probe dimensions of %s: %s", path.name, exc)
    return 1920, 1080


def _probe_has_audio(path: Path) -> bool:
    """Check if the source file has an audio stream."""
    import json

    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-print_format", "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return bool(data.get("streams"))
    except Exception:
        return False
