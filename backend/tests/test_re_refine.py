"""Plan 5A — backend tests for runner-up exposure + /re-refine endpoint."""

import uuid

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


# ---------- Task 3: _apply_speaker_assignments shared helper ----------

def test_apply_speaker_assignments_helper_exists_and_returns_results(
    icloud_base, sample_job, clean_speakers, monkeypatch
):
    """The helper extracted from /speakers/assign is callable and returns the
    same shape as the route used to return."""
    import state
    from routes.transcription import _apply_speaker_assignments
    from routes.transcription import SpeakerAssignment

    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0, "end": 5, "text": "hi",   "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
    ]
    job.speakers = [
        {"start": 0, "end": 5, "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
    ]
    state.job_store.update(job)

    # Pre-create a speaker so the assignment doesn't need create_new.
    # `speaker_store.create(speaker_id, name, folder_path)` — see
    # backend/tests/test_stores.py:15 for the established pattern.
    import uuid as _uuid
    sid = str(_uuid.uuid4())
    state.speaker_store.create(sid, "PascalWeber_TestT3", "speakers/Pascal Weber")
    clean_speakers.append(sid)

    assignments = [SpeakerAssignment(label="SPEAKER_00", speaker_name="PascalWeber_TestT3", create_new=False)]

    out = _apply_speaker_assignments(job, assignments, audio_path=None)

    assert "mapping" in out and out["mapping"] == {"SPEAKER_00": "PascalWeber_TestT3"}
    assert "results" in out and len(out["results"]) == 1
    assert out["results"][0]["label"] == "SPEAKER_00"
    assert out["results"][0]["speaker_name"] == "PascalWeber_TestT3"
    # Side effect: segment label was rewritten in-place
    assert job.segments[0]["speaker"] == "PascalWeber_TestT3"


# ---------- Task 4: POST /job/{job_id}/re-refine endpoint ----------
# Note: `client` fixture (conftest.py:115) is an httpx.AsyncClient over the
# real FastAPI app via ASGITransport. asyncio_mode = "auto" in pyproject.toml
# (line 62) so @pytest.mark.asyncio is implicit — but doesn't hurt to keep.


async def test_re_refine_happy_path_mixed_assignments(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Happy path: confirm an existing match + create a new speaker + strip another to unknown."""
    import state
    from unittest.mock import MagicMock

    # Use uniquified names to avoid colliding with leftover speakers in the
    # shared DB across test runs.
    suffix = uuid.uuid4().hex[:8]
    pascal_name = f"PascalT4_{suffix}"
    fabrice_name = f"FabriceDuboisT4_{suffix}"
    arnaud_label = f"ArnaudT4_{suffix}"

    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": pascal_name},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "text": "ciao", "speaker": arnaud_label},
    ]
    job.speakers = [
        {"start": 0, "end": 5, "speaker": pascal_name},
        {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "speaker": arnaud_label},
    ]
    job.status = "completed"
    state.job_store.update(job)

    # Pre-seed a speaker for the "confirm existing" path. SpeakerStore.create
    # returns a row dict (job_models.py:566) so unwrap speaker_id here.
    pascal_id = str(uuid.uuid4())
    state.speaker_store.create(pascal_id, pascal_name, f"speakers/{pascal_name}")
    clean_speakers.append(pascal_id)

    # Stub the executor so we don't actually fire the refinement worker
    submit_mock = MagicMock()
    monkeypatch.setattr(state, "transcription_executor", MagicMock(submit=submit_mock))

    # Stub embedding extraction so the "new:Fabrice" path doesn't need real audio
    fake_emb = MagicMock()
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            extract_embedding=MagicMock(return_value=fake_emb),
            register_speaker=MagicMock(return_value="fabrice-uuid"),
        ),
        raising=False,
    )

    body = {
        "speaker_assignments": {
            pascal_name:   pascal_id,                # confirm existing
            "SPEAKER_01":  f"new:{fabrice_name}",    # create new + embed
            arnaud_label:  "unknown",                # strip back to anonymous
        }
    }
    resp = await client.post(f"/job/{sample_job}/re-refine", json=body)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_id"] == sample_job
    assert data["status"] == "refining"
    assert data["phase"] == "refining"
    assert data["speakers_assigned"] == 3
    assert any(c["name"] == fabrice_name for c in data["speakers_created"])

    # Register Fabrice for cleanup so we don't leak rows in the shared
    # speakers DB across test runs.
    fabrice_row = state.speaker_store.get_by_name(fabrice_name)
    if fabrice_row and fabrice_row.get("speaker_id"):
        clean_speakers.append(fabrice_row["speaker_id"])

    # Refinement was dispatched on the executor
    submit_mock.assert_called_once()
    args = submit_mock.call_args[0]
    # _run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)
    assert args[1] == sample_job

    # Job state was reset
    job_after = state.job_store.get(sample_job)
    assert job_after.refinement_status == "pending"
    assert job_after.phase == "refining"


async def test_re_refine_409_when_job_not_completed(
    icloud_base, sample_job, client
):
    """409 if the job hasn't reached `completed`."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "processing"
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/re-refine",
        json={"speaker_assignments": {"SPEAKER_00": "unknown"}},
    )
    assert resp.status_code == 409
    assert "completed" in resp.text.lower()


async def test_re_refine_400_when_speaker_id_invalid(
    icloud_base, sample_job, client, monkeypatch
):
    """400 if a target speaker_id doesn't exist in the registry."""
    import state
    from unittest.mock import MagicMock

    job = state.job_store.get(sample_job)
    job.segments = [{"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"}]
    job.status = "completed"
    state.job_store.update(job)

    monkeypatch.setattr(state, "transcription_executor", MagicMock(submit=MagicMock()))

    resp = await client.post(
        f"/job/{sample_job}/re-refine",
        json={"speaker_assignments": {"SPEAKER_00": "nonexistent-uuid"}},
    )
    assert resp.status_code == 400
    assert "speaker" in resp.text.lower()


def test_runner_up_propagated_through_auto_identify(monkeypatch):
    """auto_speaker_matches entries include runner_up when registry has ≥2."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Arnaud":  _unit([0.8, 0.6, 0.0, 0.0]),
    })

    # Stub extract_speaker_embeddings to return one query embedding
    monkeypatch.setattr(
        svc, "extract_speaker_embeddings",
        lambda audio_path, turns: {"SPEAKER_00": _unit([1.0, 0.0, 0.0, 0.0])},
    )
    # Stub speaker_store.get_by_name to avoid DB requirement
    import state
    monkeypatch.setattr(state.speaker_store, "get_by_name",
                        lambda n: {"speaker_id": f"id-{n}"} if n in ("Pascal", "Arnaud") else None)
    monkeypatch.setattr(svc, "save_unknown_embedding", lambda *a, **k: None)

    result = svc.auto_identify_speakers(
        audio_path="/fake.wav",
        speaker_turns=[{"start": 0, "end": 5, "speaker": "SPEAKER_00"}],
        job_id="job-T",
    )

    assert "SPEAKER_00" in result
    entry = result["SPEAKER_00"]
    assert entry["matched"] is True
    assert entry["name"] == "Pascal"
    assert "runner_up" in entry  # field is always present (may be None)
    assert entry["runner_up"] is not None
    assert entry["runner_up"]["name"] == "Arnaud"
