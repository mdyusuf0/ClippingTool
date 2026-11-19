"""ClipFinder — transcribe: Whisper-based speech-to-word transcription."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from clipfinder.cancellation import cancellation_token

logger = logging.getLogger(__name__)


def _cache_key(path: Path, model_name: str, language: str, translate: bool) -> str:
    h = hashlib.sha1(f"{path.resolve()}{path.stat().st_size}{model_name}{language}{translate}".encode()).hexdigest()[:16]
    return h


def transcribe_video(
    path: Path,
    model_name: str = "base",
    language: str = "auto",
    translate: bool = False,
    vad_filter: bool = True,
    word_timestamps: bool = True,
    chunk_hours: float = 2.5,
    cache: bool = True,
    out_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Transcribe *path* with faster-whisper and return a list of word dicts::

        [{"text": "hello", "start": 1.23, "end": 1.56}, ...]

    Parameters
    ----------
    path:
        Input video/audio file.
    model_name:
        Whisper model size (tiny/base/small/medium/large-v2).
    language:
        Source language code or ``"auto"`` for auto-detection.
    translate:
        If True, translate to English in one pass (Whisper ``translate`` task).
    vad_filter:
        Enable faster-whisper VAD preprocessing.
    word_timestamps:
        Request per-word timestamps from Whisper.
    chunk_hours:
        Not used by faster-whisper directly but kept for API compatibility.
    cache:
        Load/save transcript JSON from *out_dir* to avoid re-transcribing.
    out_dir:
        Where to save the cached transcript JSON.

    Returns
    -------
    list of word dicts.
    """
    # Cache lookup
    if cache and out_dir is not None:
        cache_file = out_dir / f"transcript_{_cache_key(path, model_name, language, translate)}.json"
        if cache_file.exists():
            logger.info("Loading cached transcript: %s", cache_file.name)
            return json.loads(cache_file.read_text(encoding="utf-8"))

    cancellation_token.check_canceled()

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        logger.error(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        )
        return []

    # Detect CUDA GPU acceleration via ctranslate2
    device = "cpu"
    compute_type = "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            device = "cuda"
            compute_type = "float16"
    except Exception:
        pass

    logger.info("Loading Whisper model '%s' on %s (%s)…", model_name, device, compute_type)
    cpu_cores = os.cpu_count() or 4
    try:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_cores if device == "cpu" else 4,
        )
    except Exception as exc:
        if device == "cuda":
            logger.warning("CUDA load failed (%s); falling back to CPU int8…", exc)
            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_cores,
            )
        else:
            raise

    task = "translate" if translate else "transcribe"
    lang_arg = None if language == "auto" else language

    import numpy as np

    cancellation_token.check_canceled()

    # Decode audio to 16kHz mono float32 array with ffmpeg (100% reliable across all PyAV / Python versions)
    audio_input: Any = str(path)
    try:
        cmd = [
            "ffmpeg", "-nostdin", "-threads", "0", "-i", str(path),
            "-vn", "-ar", "16000", "-ac", "1", "-f", "s16le", "-"
        ]
        res = cancellation_token.run_command(cmd, capture_output=True, check=True)
        if res.stdout:
            audio_input = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as exc:
        if cancellation_token.is_canceled():
            raise
        logger.debug("ffmpeg audio decode fallback to str path: %s", exc)

    cancellation_token.check_canceled()
    logger.info("Transcribing %s (task=%s, lang=%s)…", path.name, task, lang_arg or "auto")
    segments_gen, info = model.transcribe(
        audio_input,
        task=task,
        language=lang_arg,
        vad_filter=vad_filter,
        word_timestamps=word_timestamps,
    )

    words: list[dict[str, Any]] = []
    for segment in segments_gen:
        cancellation_token.check_canceled()
        if word_timestamps and segment.words:
            for w in segment.words:
                words.append({"text": w.word.strip(), "start": w.start, "end": w.end})
        else:
            # Fallback: treat whole segment as one "word"
            words.append({"text": segment.text.strip(), "start": segment.start, "end": segment.end})

    logger.info("Transcription complete — %d word tokens.", len(words))

    # Cache save
    if cache and out_dir is not None:
        cache_file = out_dir / f"transcript_{_cache_key(path, model_name, language, translate)}.json"
        cache_file.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved transcript cache: %s", cache_file.name)

    return words
