"""ClipFinder — score: scene detection, audio energy, and clip scoring."""

from __future__ import annotations

import logging
import subprocess
import json
from pathlib import Path
from typing import Any

import numpy as np

from clipfinder.cancellation import cancellation_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scene change detection (ffmpeg scene filter)
# ---------------------------------------------------------------------------


def detect_scene_changes(path: Path, threshold: float = 0.3) -> list[float]:
    """
    Use ffmpeg's ``select`` filter on a downscaled thumbnail stream to detect scene changes rapidly.

    Returns a sorted list of timestamps (seconds) where a scene cut occurs.

    Parameters
    ----------
    path:
        Input video file.
    threshold:
        Scene change score threshold (0–1). Lower = more sensitive.
    """
    cancellation_token.check_canceled()
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-threads", "0",
        "-i", str(path),
        "-an",
        "-vf", f"scale=240:-1,select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-",
    ]
    try:
        result = cancellation_token.run_command(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # showinfo exits 0 but writes to stderr
        )
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found — install ffmpeg.")

    timestamps: list[float] = []
    for line in result.stderr.splitlines():
        # showinfo lines look like: ... pts_time:12.345 ...
        if "pts_time:" in line:
            try:
                ts_str = line.split("pts_time:")[1].split()[0]
                timestamps.append(float(ts_str))
            except (IndexError, ValueError):
                continue

    timestamps.sort()
    logger.debug("Detected %d scene changes in %s.", len(timestamps), path.name)
    return timestamps


# ---------------------------------------------------------------------------
# Audio energy (via ffmpeg + numpy)
# ---------------------------------------------------------------------------

_SAMPLE_RATE = 16000
_HOP_DURATION = 0.5  # seconds per energy sample


def compute_audio_energy(path: Path) -> list[tuple[float, float]]:
    """
    Extract mono PCM audio and compute RMS energy in 0.5-second windows.

    Returns a list of ``(time_seconds, rms_energy)`` tuples.
    If the file has no audio stream, returns an empty list.
    """
    # Probe first to check for audio
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-print_format", "json",
        str(path),
    ]
    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
        probe_data = json.loads(probe_result.stdout or "{}")
        if not probe_data.get("streams"):
            logger.debug("No audio stream in %s — skipping energy computation.", path.name)
            return []
    except Exception:
        pass

    cancellation_token.check_canceled()
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-threads", "0",
        "-i", str(path),
        "-vn",
        "-ac", "1",
        "-ar", str(_SAMPLE_RATE),
        "-f", "f32le",
        "-",
    ]
    try:
        result = cancellation_token.run_command(cmd, capture_output=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found — install ffmpeg.")

    if not result.stdout:
        logger.warning("No audio data returned by ffmpeg for %s.", path.name)
        return []

    samples = np.frombuffer(result.stdout, dtype=np.float32)
    hop_samples = int(_SAMPLE_RATE * _HOP_DURATION)
    energies: list[tuple[float, float]] = []

    for i in range(0, len(samples), hop_samples):
        chunk = samples[i : i + hop_samples]
        if len(chunk) == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        time_s = i / _SAMPLE_RATE
        energies.append((time_s, rms))

    logger.debug("Computed %d audio energy samples for %s.", len(energies), path.name)
    return energies


# ---------------------------------------------------------------------------
# Clip scoring
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS: dict[str, float] = {
    "loudness": 0.25,
    "speech_rate": 0.20,
    "hook_word": 0.20,
    "punctuation": 0.15,
    "scene_change": 0.20,
}

_PUNCTUATION_CHARS = frozenset("!?.,;:")
_PROFANITY_LIST = frozenset(
    ["fuck", "shit", "ass", "bitch", "crap", "damn", "hell"]
)


def _normalise(values: list[float]) -> list[float]:
    """Min–max normalise a list of floats to [0, 1]."""
    if not values:
        return values
    lo, hi = min(values), max(values)
    rng = hi - lo
    if rng == 0:
        return [0.5] * len(values)
    return [(v - lo) / rng for v in values]


def score_clips(
    words: list[dict[str, Any]],
    audio_energy: list[tuple[float, float]],
    scene_changes: list[float],
    hook_words: list[str],
    min_dur: int = 15,
    max_dur: int = 45,
    top_n: int = 5,
    scoring_weights: dict[str, float] | None = None,
    video_duration: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Score candidate windows across the video timeline and return the top N
    non-overlapping clips.

    Algorithm
    ---------
    1. Slide a window of ``(min_dur + max_dur) / 2`` seconds every ``min_dur / 2``
       seconds across the timeline.
    2. For each window compute five sub-scores:
       - **loudness**: mean RMS energy inside the window (normalised).
       - **speech_rate**: words-per-second inside the window (normalised).
       - **hook_word**: fraction of hook words matched (normalised).
       - **punctuation**: density of punctuation / exclamation markers.
       - **scene_change**: number of scene cuts inside the window (normalised).
    3. Weighted sum → composite score.
    4. Greedy non-overlapping selection of top N windows.

    Returns a list of clip dicts with keys: start, end, score, matched_hooks.
    """
    weights = {**_DEFAULT_WEIGHTS, **(scoring_weights or {})}

    # Energy lookup: bin → RMS
    energy_map: dict[int, float] = {}
    for t, rms in audio_energy:
        bin_idx = int(t / _HOP_DURATION)
        energy_map[bin_idx] = rms

    hook_lower = [h.lower() for h in hook_words]

    # Determine video duration from words if not provided
    if video_duration <= 0:
        if words:
            video_duration = max(w.get("end", 0.0) for w in words)
        elif audio_energy:
            video_duration = audio_energy[-1][0] + _HOP_DURATION
        else:
            return []

    win_dur = (min_dur + max_dur) / 2.0
    step = max(min_dur / 2.0, 1.0)

    candidates: list[dict[str, Any]] = []
    t = 0.0
    while t + min_dur <= video_duration:
        cancellation_token.check_canceled()
        w_start = t
        w_end = min(t + win_dur, video_duration)
        actual_dur = w_end - w_start
        if actual_dur < min_dur:
            break

        # Words in window
        win_words = [w for w in words if w_start <= w.get("start", 0.0) < w_end]
        word_texts = [w.get("text", "").lower() for w in win_words]

        # Sub-scores (raw, before normalisation across all windows)
        # Loudness
        bins = range(int(w_start / _HOP_DURATION), int(w_end / _HOP_DURATION) + 1)
        rms_vals = [energy_map[b] for b in bins if b in energy_map]
        loudness_raw = float(np.mean(rms_vals)) if rms_vals else 0.0

        # Speech rate (words per second)
        speech_rate_raw = len(win_words) / actual_dur if actual_dur > 0 else 0.0

        # Hook words
        matched: list[str] = []
        for hw in hook_lower:
            hw_tokens = hw.split()
            if len(hw_tokens) == 1:
                if hw in word_texts:
                    matched.append(hw)
            else:
                # multi-word phrase: search in joined text
                joined = " ".join(word_texts)
                if hw in joined:
                    matched.append(hw)
        hook_raw = len(matched) / max(len(hook_lower), 1)

        # Punctuation density (exclamation / question)
        punct_texts = " ".join(word_texts)
        punct_count = sum(1 for c in punct_texts if c in _PUNCTUATION_CHARS)
        punct_raw = punct_count / max(len(punct_texts), 1)

        # Scene changes
        scene_raw = sum(1 for sc in scene_changes if w_start <= sc < w_end)

        candidates.append(
            {
                "start": w_start,
                "end": w_end,
                "matched_hooks": list(set(matched)),
                "_loudness": loudness_raw,
                "_speech_rate": speech_rate_raw,
                "_hook_word": hook_raw,
                "_punctuation": punct_raw,
                "_scene_change": float(scene_raw),
            }
        )
        t += step

    if not candidates:
        # No-speech fallback: split video into evenly spaced windows
        logger.info("No candidate windows from words — using audio-energy fallback.")
        return _fallback_energy_clips(
            audio_energy=audio_energy,
            min_dur=min_dur,
            max_dur=max_dur,
            top_n=top_n,
            video_duration=video_duration,
        )

    # Normalise each sub-score dimension
    for dim in ("_loudness", "_speech_rate", "_hook_word", "_punctuation", "_scene_change"):
        raw_vals = [c[dim] for c in candidates]
        normed = _normalise(raw_vals)
        for c, nv in zip(candidates, normed):
            c[dim] = nv

    # Composite score
    for c in candidates:
        c["score"] = (
            weights.get("loudness", 0.25) * c["_loudness"]
            + weights.get("speech_rate", 0.20) * c["_speech_rate"]
            + weights.get("hook_word", 0.20) * c["_hook_word"]
            + weights.get("punctuation", 0.15) * c["_punctuation"]
            + weights.get("scene_change", 0.20) * c["_scene_change"]
        )

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Greedy non-overlapping selection
    selected: list[dict[str, Any]] = []
    for cand in candidates:
        if len(selected) >= top_n:
            break
        overlaps = any(
            cand["start"] < sel["end"] and cand["end"] > sel["start"]
            for sel in selected
        )
        if not overlaps:
            # Clamp end to max_dur
            cand["end"] = min(cand["start"] + max_dur, video_duration, cand["end"])
            # Clean internal keys
            for k in list(cand.keys()):
                if k.startswith("_"):
                    del cand[k]
            selected.append(cand)

    # Sort chronologically for output
    selected.sort(key=lambda x: x["start"])
    return selected


def _fallback_energy_clips(
    audio_energy: list[tuple[float, float]],
    min_dur: int,
    max_dur: int,
    top_n: int,
    video_duration: float,
) -> list[dict[str, Any]]:
    """Select clips based purely on audio energy when no words are available."""
    if not audio_energy or video_duration <= 0:
        return []

    win_dur = (min_dur + max_dur) / 2.0
    step = max(min_dur / 2.0, 1.0)

    energy_map: dict[int, float] = {int(t / _HOP_DURATION): rms for t, rms in audio_energy}

    candidates = []
    t = 0.0
    while t + min_dur <= video_duration:
        w_end = min(t + win_dur, video_duration)
        bins = range(int(t / _HOP_DURATION), int(w_end / _HOP_DURATION) + 1)
        rms_vals = [energy_map[b] for b in bins if b in energy_map]
        score = float(np.mean(rms_vals)) if rms_vals else 0.0
        candidates.append({"start": t, "end": w_end, "score": score, "matched_hooks": []})
        t += step

    if not candidates:
        return []

    raw_scores = [c["score"] for c in candidates]
    normed = _normalise(raw_scores)
    for c, nv in zip(candidates, normed):
        c["score"] = nv

    candidates.sort(key=lambda x: x["score"], reverse=True)

    selected: list[dict[str, Any]] = []
    for cand in candidates:
        if len(selected) >= top_n:
            break
        if not any(
            cand["start"] < sel["end"] and cand["end"] > sel["start"]
            for sel in selected
        ):
            selected.append(cand)

    selected.sort(key=lambda x: x["start"])
    return selected
