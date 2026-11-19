"""
clipfinder.probe
~~~~~~~~~~~~~~~~
Thin wrapper around ``ffprobe`` that extracts structured metadata from a
video file and returns it as a :class:`VideoInfo` dataclass.

Usage::

    from pathlib import Path
    from clipfinder.probe import probe_video

    info = probe_video(Path("my_video.mp4"))
    print(info.duration, info.fps, info.has_audio)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class VideoInfo:
    """Structured metadata for a single video file.

    Attributes
    ----------
    path:
        Absolute path to the source file.
    duration:
        Total duration in seconds (float).
    width:
        Frame width in pixels **after** rotation is applied.
    height:
        Frame height in pixels **after** rotation is applied.
    fps:
        Frames per second derived from ``r_frame_rate`` (handles VFR streams).
    rotation:
        Display rotation in degrees clockwise: 0, 90, 180, or 270.
    has_audio:
        ``True`` if at least one audio stream was found.
    audio_stream_index:
        Index of the best audio stream (highest bit-rate), or ``-1``.
    audio_streams:
        Raw list of all audio stream dicts from ffprobe JSON output.
    is_portrait:
        ``True`` when the effective height > effective width.
    is_square:
        ``True`` when effective width == effective height.
    format_name:
        Container format string (e.g. ``"mov,mp4,m4a,3gp,3g2,mj2"``).
    bit_rate:
        Overall container bit-rate in bits per second (0 if unavailable).
    """

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    rotation: int
    has_audio: bool
    audio_stream_index: int
    audio_streams: list[dict[str, Any]]
    is_portrait: bool
    is_square: bool
    format_name: str
    bit_rate: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_fps(r_frame_rate: str) -> float:
    """Parse an ``r_frame_rate`` string such as ``"30000/1001"`` → float.

    Falls back to 0.0 on any parse error.
    """
    try:
        frac = Fraction(r_frame_rate)
        return float(frac)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _parse_rotation(stream: dict[str, Any]) -> int:
    """Extract the display rotation (degrees) from a video stream dict.

    Checks two locations (in order):
    1. ``stream["tags"]["rotate"]``  – older mp4/mov metadata
    2. ``stream["side_data_list"]``  – newer ISOBMFF display-matrix side data

    The ``rotation`` value in ``side_data_list`` uses the **inverse**
    convention (counter-clockwise), so it is negated.

    Returns 0, 90, 180, or 270.
    """
    # Location 1 – tags.rotate
    tags: dict[str, str] = stream.get("tags", {})
    rotate_tag = tags.get("rotate", "")
    if rotate_tag:
        try:
            return int(rotate_tag) % 360
        except ValueError:
            pass

    # Location 2 – side_data_list with type "Display Matrix"
    for side_data in stream.get("side_data_list", []):
        if "rotation" in side_data:
            try:
                # ffprobe reports counter-clockwise; negate to get CW.
                ccw = int(side_data["rotation"])
                cw = (-ccw) % 360
                return cw
            except (ValueError, TypeError):
                pass

    return 0


def _best_audio_stream(audio_streams: list[dict[str, Any]]) -> int:
    """Return the stream *index* (``codec_type == "audio"``) with the highest
    bit-rate, or ``-1`` if *audio_streams* is empty.

    Parameters
    ----------
    audio_streams:
        List of raw ffprobe stream dicts filtered to audio streams.

    Returns
    -------
    int
        ``stream["index"]`` of the winner, or ``-1``.
    """
    if not audio_streams:
        return -1

    def _bit_rate(s: dict[str, Any]) -> int:
        try:
            return int(s.get("bit_rate", 0))
        except (ValueError, TypeError):
            return 0

    best = max(audio_streams, key=_bit_rate)
    return int(best["index"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def probe_video(path: Path) -> VideoInfo:
    """Run ``ffprobe`` on *path* and return structured :class:`VideoInfo`.

    Parameters
    ----------
    path:
        Path to the video file to probe.

    Returns
    -------
    VideoInfo
        Populated dataclass with metadata from ffprobe.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If ffprobe fails (non-zero exit code, unreadable JSON) **or** if the
        probed duration is 0 / unavailable — which typically indicates a
        corrupt or unsupported file.
    RuntimeError("no_audio")
        Raised when no audio stream is present and the caller needs to react
        (e.g. skip transcription).  Callers that do not care about audio
        can catch and ignore this.
    """
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "ffprobe is not installed or not on PATH. "
            "Install ffmpeg (which includes ffprobe) for your platform."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"ffprobe timed out while probing {path}"
        ) from exc

    if result.returncode != 0:
        stderr_text = result.stderr.decode(errors="replace").strip()
        raise ValueError(
            f"ffprobe exited with code {result.returncode} for {path}.\n"
            f"stderr: {stderr_text}"
        )

    try:
        probe_data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"ffprobe produced invalid JSON for {path}: {exc}"
        ) from exc

    # ------------------------------------------------------------------
    # Parse format block
    # ------------------------------------------------------------------
    fmt: dict[str, Any] = probe_data.get("format", {})
    format_name: str = fmt.get("format_name", "unknown")

    try:
        duration = float(fmt.get("duration", 0) or 0)
    except (ValueError, TypeError):
        duration = 0.0

    try:
        bit_rate = int(fmt.get("bit_rate", 0) or 0)
    except (ValueError, TypeError):
        bit_rate = 0

    # ------------------------------------------------------------------
    # Partition streams
    # ------------------------------------------------------------------
    all_streams: list[dict[str, Any]] = probe_data.get("streams", [])
    video_streams = [s for s in all_streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in all_streams if s.get("codec_type") == "audio"]

    # ------------------------------------------------------------------
    # Video stream metadata
    # ------------------------------------------------------------------
    if not video_streams:
        raise ValueError(
            f"No video stream found in {path}. The file may be corrupt or "
            "contain only audio."
        )

    # Use the first video stream (typically the only one).
    vs: dict[str, Any] = video_streams[0]

    raw_width: int = int(vs.get("width", 0) or 0)
    raw_height: int = int(vs.get("height", 0) or 0)
    fps: float = _parse_fps(vs.get("r_frame_rate", "0/1"))

    # Prefer stream-level duration over format-level if more accurate.
    stream_duration_str = vs.get("duration", "") or ""
    if stream_duration_str:
        try:
            stream_duration = float(stream_duration_str)
            if stream_duration > 0:
                duration = stream_duration
        except ValueError:
            pass

    if duration == 0:
        raise ValueError(
            f"Could not determine duration of {path}. "
            "The file may be corrupt, truncated, or in an unsupported format."
        )

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    rotation: int = _parse_rotation(vs)

    # Apply rotation: swap dimensions for 90 / 270 degree rotations so that
    # `width` and `height` reflect the *display* (viewer-facing) geometry.
    if rotation in (90, 270):
        effective_width, effective_height = raw_height, raw_width
    else:
        effective_width, effective_height = raw_width, raw_height

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    has_audio = len(audio_streams) > 0
    audio_stream_index = _best_audio_stream(audio_streams)

    # ------------------------------------------------------------------
    # Derived flags
    # ------------------------------------------------------------------
    is_portrait = effective_height > effective_width
    is_square = effective_width == effective_height

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------
    info = VideoInfo(
        path=path.resolve(),
        duration=duration,
        width=effective_width,
        height=effective_height,
        fps=fps,
        rotation=rotation,
        has_audio=has_audio,
        audio_stream_index=audio_stream_index,
        audio_streams=audio_streams,
        is_portrait=is_portrait,
        is_square=is_square,
        format_name=format_name,
        bit_rate=bit_rate,
    )

    # Raise no_audio sentinel so callers that require audio can react.
    if not has_audio:
        raise RuntimeError("no_audio")

    return info
