"""Scope-resolution tests for the pre-pick aware voice auto-match.

Covers the decision logic in routes.transcription._resolve_match_scope and
the pool-filtering in SpeakerEmbeddingService.match_speaker. The actual
pyannote embedding extraction is NOT exercised here (requires a GPU + an
audio file); we feed synthetic 512-dim unit vectors to the matcher instead.
"""

import numpy as np
import pytest

from routes.transcription import _resolve_match_scope
from services.speaker_embedding import SpeakerEmbeddingService


def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------- scope resolver ----------

def test_scope_exact_count_returns_scoped():
    settings = {"speaker_ids": ["a", "b"], "num_speakers": 2}
    restrict, prefer, mode = _resolve_match_scope(settings)
    assert restrict == ["a", "b"]
    assert prefer is None
    assert mode == "scoped"


def test_scope_partial_picks_returns_global_prefer():
    settings = {"speaker_ids": ["a"], "num_speakers": 3}
    restrict, prefer, mode = _resolve_match_scope(settings)
    assert restrict is None
    assert prefer == ["a"]
    assert mode == "global-prefer"


def test_scope_no_picks_returns_global():
    settings = {"speaker_ids": [], "num_speakers": 2}
    restrict, prefer, mode = _resolve_match_scope(settings)
    assert restrict is None
    assert prefer is None
    assert mode == "global"


def test_scope_auto_detect_with_picks_is_global_prefer():
    settings = {"speaker_ids": ["a", "b"], "num_speakers": None}
    restrict, prefer, mode = _resolve_match_scope(settings)
    assert restrict is None
    assert prefer == ["a", "b"]
    assert mode == "global-prefer"


def test_scope_auto_detect_string_is_handled():
    settings = {"speaker_ids": ["a"], "num_speakers": "auto"}
    _, _, mode = _resolve_match_scope(settings)
    assert mode == "global-prefer"


def test_scope_missing_settings_is_global():
    restrict, prefer, mode = _resolve_match_scope(None)
    assert restrict is None and prefer is None and mode == "global"


# ---------- match_speaker pool-filter + tiebreaker ----------

@pytest.fixture
def svc_with_embeddings(monkeypatch):
    svc = SpeakerEmbeddingService()
    # Inject 3 synthetic embeddings with known cosine relationships:
    #   'Alice' : [1, 0, ...]
    #   'Bob'   : [0.98, 0.2, ...] ≈ very close to Alice
    #   'Carol' : [0, 1, ...]      ≈ orthogonal to Alice
    dim = SpeakerEmbeddingService.EMBEDDING_DIM
    alice = _unit(np.concatenate([[1.0, 0.0], np.zeros(dim - 2)]))
    bob = _unit(np.concatenate([[0.98, 0.2], np.zeros(dim - 2)]))
    carol = _unit(np.concatenate([[0.0, 1.0], np.zeros(dim - 2)]))
    svc._known_embeddings = {"Alice": alice, "Bob": bob, "Carol": carol}
    svc._cache_loaded = True
    return svc, alice


def test_match_restrict_excludes_better_global_candidate(svc_with_embeddings):
    svc, probe = svc_with_embeddings
    # Probe is identical to Alice; globally Alice wins.
    name, _, _ = svc.match_speaker(probe)
    assert name == "Alice"
    # Restrict to Carol only → nothing above threshold.
    name, score, _ = svc.match_speaker(probe, restrict_to_names=["Carol"])
    assert name is None
    # And the probe's similarity to Carol is ~0 (orthogonal).
    assert score < 0.1


def test_match_prefer_swaps_in_pick_within_gap(svc_with_embeddings):
    svc, probe = svc_with_embeddings
    # Alice and Bob are within 0.03 cosine; prefer Bob → should bump Bob.
    name, _, _ = svc.match_speaker(probe, prefer_names=["Bob"])
    assert name == "Bob"


def test_match_prefer_does_not_override_distant_gap(svc_with_embeddings):
    svc, probe = svc_with_embeddings
    # Prefer Carol (orthogonal) → Alice still wins because Carol is far outside gap.
    name, _, _ = svc.match_speaker(probe, prefer_names=["Carol"])
    assert name == "Alice"


def test_match_restrict_never_mutates_cache(svc_with_embeddings):
    svc, probe = svc_with_embeddings
    before = set(svc._known_embeddings.keys())
    svc.match_speaker(probe, restrict_to_names=["Alice"])
    svc.match_speaker(probe, restrict_to_names=["Carol"])
    after = set(svc._known_embeddings.keys())
    assert before == after == {"Alice", "Bob", "Carol"}
