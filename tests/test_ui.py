"""Unit tests for clipfinder.ui (GTA VI Clipping Studio)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest


def test_category_map_contains_gta6_categories() -> None:
    """Verify CATEGORY_MAP has all required GTA 6 categories."""
    from clipfinder.ui import CATEGORY_MAP

    keys = set(CATEGORY_MAP.values())
    expected = {"action", "chases", "funny", "serious", "sad", "cinematic", "stunts", "gaming"}
    assert expected.issubset(keys), f"Missing categories: {expected - keys}"


def test_ui_empty_inputs_returns_warning() -> None:
    """_run_pipeline should return a warning if no URL or uploaded file is provided."""
    from clipfinder.ui import _run_pipeline, DEFAULT_CATEGORY

    v1, v2, v3, v4, v5, gallery, df, z, status, cards = _run_pipeline(
        urls_text="",
        uploaded_files=None,
        category_label=DEFAULT_CATEGORY,
        has_permission=True,
        n_clips=4,
        min_duration=15,
        max_duration=35,
        style="blur",
        captions_preset="vice_city",
        mask_profanity=True,
        hook_text="",
        model="base",
        language="auto",
        gemini_api_key="",
    )
    assert "No inputs provided" in status
    assert v1 is None
    assert z is None


def test_ui_permission_gate_refusal() -> None:
    """_run_pipeline should refuse external URL processing if has_permission is False."""
    from clipfinder.ui import _run_pipeline, DEFAULT_CATEGORY

    v1, v2, v3, v4, v5, gallery, df, z, status, cards = _run_pipeline(
        urls_text="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        uploaded_files=None,
        category_label=DEFAULT_CATEGORY,
        has_permission=False,
        n_clips=4,
        min_duration=15,
        max_duration=35,
        style="blur",
        captions_preset="vice_city",
        mask_profanity=True,
        hook_text="",
        model="base",
        language="auto",
        gemini_api_key="",
    )
    assert "Permission required" in status
    assert v1 is None
    assert z is None


def test_cancellation_manager_basic() -> None:
    """Verify CancellationManager flags and exceptions."""
    from clipfinder.cancellation import CancellationManager, CancellationError

    mgr = CancellationManager()
    assert not mgr.is_canceled()
    mgr.check_canceled()  # should not raise

    mgr.cancel()
    assert mgr.is_canceled()
    with pytest.raises(CancellationError):
        mgr.check_canceled()

    mgr.reset()
    assert not mgr.is_canceled()


def test_ui_cancellation_stops_pipeline(tmp_path: Path) -> None:
    """_run_pipeline should abort midway and return clean status when canceled."""
    from clipfinder.ui import _run_pipeline, DEFAULT_CATEGORY
    from clipfinder.cancellation import cancellation_token

    # Create a small dummy file
    dummy = tmp_path / "dummy.mp4"
    dummy.write_bytes(b"dummy")

    with patch("clipfinder.ingest.classify_input", return_value=("file", str(dummy))), \
         patch("clipfinder.ingest.probe_video", side_effect=lambda p: cancellation_token.cancel() or {"duration": 60}):
        v1, v2, v3, v4, v5, gallery, df, z, status, cards = _run_pipeline(
            urls_text=str(dummy),
            uploaded_files=None,
            category_label=DEFAULT_CATEGORY,
            has_permission=True,
            n_clips=2,
            min_duration=10,
            max_duration=30,
            style="blur",
            captions_preset="vice_city",
            mask_profanity=True,
            hook_text="",
            model="tiny",
            language="auto",
            gemini_api_key="",
        )
        assert "cancelled by user" in status.lower()
        assert v1 is None
