"""Plan 5A — backend tests for runner-up exposure + /re-refine endpoint."""

import numpy as np
import pytest

from services.speaker_embedding import SpeakerEmbeddingService


def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------- Task 2: runner-up exposure in match_speaker ----------

def _make_service_with_speakers(monkeypatch, embeddings):
    """Build a SpeakerEmbeddingService with a pre-seeded embedding cache.

    Critical: `_load_known_embeddings` clears `_known_embeddings` on every
    call (services/speaker_embedding.py:59), so we monkeypatch it to a
    no-op after seeding the dict.
    """
    svc = SpeakerEmbeddingService()
    svc._known_embeddings = dict(embeddings)
    monkeypatch.setattr(svc, "_load_known_embeddings", lambda: None)
    return svc


def test_match_speaker_returns_runner_up_when_two_qualifying(monkeypatch):
    """With 2+ speakers above the runner-up threshold, returns 2nd-best."""
    import state
    # The runner-up dict is built by looking up `speaker_id` via
    # state.speaker_store.get_by_name(second_name). We don't seed the store,
    # so stub it to None — the test's intent is to verify the runner-up name
    # and confidence; speaker_id is expected to be None.
    monkeypatch.setattr(state.speaker_store, "get_by_name", lambda n: None)

    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Arnaud":  _unit([0.8, 0.6, 0.0, 0.0]),  # ~0.8 cosine to query
        "Fabrice": _unit([0.0, 0.0, 1.0, 0.0]),  # ~0.0 cosine → below 0.4 threshold
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert score > 0.99
    assert runner_up is not None
    assert runner_up["name"] == "Arnaud"
    assert runner_up["speaker_id"] is None  # store stubbed to None
    assert 0.7 < runner_up["confidence"] < 0.85
    # Fabrice should NOT appear (below 0.4 threshold)
    assert runner_up["name"] != "Fabrice"


def test_match_speaker_returns_none_runner_up_when_only_one_speaker(monkeypatch):
    """Single-speaker registry has no possible runner-up."""
    import state
    monkeypatch.setattr(state.speaker_store, "get_by_name", lambda n: None)

    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal": _unit([1.0, 0.0, 0.0, 0.0]),
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert runner_up is None


def test_match_speaker_runner_up_below_threshold_returns_none(monkeypatch):
    """Runner-up below RUNNER_UP_THRESHOLD (0.4) is suppressed."""
    import state
    monkeypatch.setattr(state.speaker_store, "get_by_name", lambda n: None)

    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Fabrice": _unit([0.0, 0.0, 0.0, 1.0]),  # orthogonal, cosine = 0
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert runner_up is None  # Fabrice's 0.0 < 0.4 threshold


def test_match_speaker_returns_three_tuple_when_no_match(monkeypatch):
    """Even when no match qualifies, return shape is still 3-tuple (None, score, None)."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal": _unit([0.0, 0.0, 0.0, 1.0]),
    })

    result = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert len(result) == 3
    name, score, runner_up = result
    assert name is None
    assert runner_up is None
