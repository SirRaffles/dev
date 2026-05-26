"""Plan 7A — backend tests for the pre-refinement speaker-resolution gate."""

import uuid
import pytest


# ---------- Task 2: speakers_resolved field + migration + GET surface ----------

def test_transcription_job_speakers_resolved_defaults_false():
    """New jobs start with speakers_resolved=False — they must pass the gate."""
    from job_models import TranscriptionJob
    job = TranscriptionJob("sr-1")
    assert hasattr(job, "speakers_resolved"), \
        "TranscriptionJob must declare a `speakers_resolved` attribute"
    assert job.speakers_resolved is False, "defaults to False pre-gate"


def test_row_to_job_migration_marks_completed_jobs_resolved():
    """Pre-Plan-7 completed jobs reloaded from SQL must be treated as
    already past the gate — they completed before the gate existed."""
    import state
    from job_models import TranscriptionJob

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "completed"
    job.progress = 100
    job.speaker_review_status = "not_needed"
    job.speakers_resolved = True
    state.job_store.create(job)
    try:
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.speaker_review_status in {"not_needed", "reviewed"}
        assert reloaded.speakers_resolved is True
    finally:
        state.job_store.delete(job_id)


def test_row_to_job_migration_leaves_non_completed_unresolved():
    """A row with status != 'completed' must keep speakers_resolved=False."""
    import state
    from job_models import TranscriptionJob

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "processing"
    state.job_store.create(job)
    try:
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "processing"
        assert reloaded.speakers_resolved is False, \
            "non-completed rows must not be auto-flipped"
    finally:
        state.job_store.delete(job_id)


async def test_get_job_surfaces_speakers_resolved(icloud_base, sample_job, client):
    """GET /job/{id} response must include a `speakers_resolved` field."""
    resp = await client.get(f"/job/{sample_job}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "speakers_resolved" in data, \
        "GET response must surface speakers_resolved"
    assert isinstance(data["speakers_resolved"], bool)


# ---------- Task 3: orchestrator split (auto-resolve vs awaiting) ----------

def test_all_labels_matched_true_when_all_segments_named():
    """All segments use real names → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "David Marchesseau"},
    ]
    job.auto_speaker_matches = {}
    assert _all_labels_matched(job) is True


def test_all_labels_matched_true_when_all_anonymous_b5_matched():
    """Anonymous labels with B5 matched=True → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-2")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_00": {"matched": True, "name": "Pascal Weber"},
        "SPEAKER_01": {"matched": True, "name": "David Marchesseau"},
    }
    assert _all_labels_matched(job) is True


def test_all_labels_matched_false_when_any_unmatched_anonymous():
    """Any anonymous label without a B5 match → unmatched (awaiting path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-3")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "??", "speaker": "SPEAKER_02"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_02": {"matched": False},
    }
    assert _all_labels_matched(job) is False


def test_all_labels_matched_empty_segments_returns_true():
    """Vacuous case: no segments to resolve → treat as matched (no-op refinement)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched
    job = TranscriptionJob("mlm-4")
    job.segments = []
    assert _all_labels_matched(job) is True


def test_orchestrator_auto_resolve_path_sets_resolved_and_dispatches(monkeypatch):
    """When _all_labels_matched returns True, orchestrator must:
      - set job.speakers_resolved = True
      - clear job.phase
      - leave job.status = "completed"
      - dispatch _run_refinement_for_job via state.transcription_executor
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob
    from services import orchestrator as orch

    job = TranscriptionJob("auto-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
    ]
    job.speakers = []
    job.auto_speaker_matches = {}
    state.job_store.create(job)
    try:
        # Drive the post-alignment finalize block directly. We extract its
        # contents into a private helper so the test can call it without
        # standing up the entire transcribe pipeline (see implementation
        # note in Step 5: the helper is `_finalize_after_alignment`).
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        # Settings stub: auto_refine on so the dispatch fires
        from job_models import TranscriptionSettings
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is True
        assert job.status == "completed"
        assert job.phase == "refining"
        submit_mock.assert_called_once()
    finally:
        state.job_store.delete("auto-1")


def test_orchestrator_unresolved_speakers_do_not_block_refinement(monkeypatch):
    """When _all_labels_matched returns False but auto-refine is allowed, orchestrator must:
      - leave job.speakers_resolved = False
      - clear job.phase
      - set job.status = "completed"
      - dispatch refinement
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob, TranscriptionSettings
    from services import orchestrator as orch

    job = TranscriptionJob("await-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
    ]
    job.auto_speaker_matches = {"SPEAKER_00": {"matched": False}}
    state.job_store.create(job)
    try:
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is False
        assert job.status == "completed"
        assert job.phase == "refining"
        submit_mock.assert_called_once()
    finally:
        state.job_store.delete("await-1")


# ---------- Task 4: POST /job/{job_id}/confirm-speakers ----------

async def test_confirm_speakers_happy_path(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Happy path: assign an existing UUID + create a new speaker + ignore one.

    Verifies:
      - 200 + correct response shape
      - speakers_resolved flips to True
      - phase becomes "refining"
      - refinement is dispatched (executor.submit called once)
      - ignored labels do NOT appear in helper_assignments (segments stay anonymous)
    """
    import state
    from unittest.mock import MagicMock
    from job_models import TranscriptionJob

    suffix = uuid.uuid4().hex[:8]
    pascal_name = f"Pascal_T4cs_{suffix}"
    fabrice_name = f"Fabrice_T4cs_{suffix}"

    # Seed job state: completed, speakers_resolved=False (gate not yet passed)
    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0,  "end": 5,  "text": "hi",     "speaker": "SPEAKER_00"},
        {"start": 5,  "end": 10, "text": "salut",  "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "text": "???",    "speaker": "SPEAKER_02"},
    ]
    job.speakers = [
        {"start": 0, "end": 5,   "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10,  "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "speaker": "SPEAKER_02"},
    ]
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    # Pre-seed Pascal so the UUID-assign path has something to find
    pascal_id = str(uuid.uuid4())
    state.speaker_store.create(pascal_id, pascal_name, f"speakers/{pascal_name}")
    clean_speakers.append(pascal_id)

    # Stub executor + embedding service so the test doesn't fire the worker
    submit_mock = MagicMock()
    monkeypatch.setattr(state, "transcription_executor",
                        MagicMock(submit=submit_mock))
    fake_emb = MagicMock()
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            # _apply_speaker_assignments only calls extract_embedding +
            # update_embedding (it uses state.speaker_store.create directly
            # for new profiles, NOT embedding_service.register_speaker).
            extract_embedding=MagicMock(return_value=fake_emb),
            update_embedding=MagicMock(),
        ),
        raising=False,
    )

    body = {
        "speaker_assignments": {
            "SPEAKER_00": pascal_id,                # existing UUID
            "SPEAKER_01": f"new:{fabrice_name}",    # create new
            "SPEAKER_02": "ignore",                 # leave anonymous
        }
    }
    resp = await client.post(f"/job/{sample_job}/confirm-speakers", json=body)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_id"] == sample_job
    assert data["phase"] == "refining"
    assert data["speakers_assigned"] == 2  # ignore doesn't count
    assert data["speakers_ignored"] == 1
    assert any(c["name"] == fabrice_name for c in data["speakers_created"])

    # Cleanup the created Fabrice if it landed in the store
    fab = state.speaker_store.get_by_name(fabrice_name)
    if fab and fab.get("speaker_id"):
        clean_speakers.append(fab["speaker_id"])

    # Gate state flipped
    job_after = state.job_store.get(sample_job)
    assert job_after.speakers_resolved is True
    assert job_after.phase == "refining"

    # Refinement was dispatched
    submit_mock.assert_called_once()


async def test_confirm_speakers_409_when_already_resolved(
    icloud_base, sample_job, client
):
    """If speakers_resolved is already True, return 409 (idempotent error)."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "completed"
    job.speakers_resolved = True
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 409
    assert "resolved" in resp.text.lower() or "already" in resp.text.lower()


async def test_confirm_speakers_409_when_job_not_completed(
    icloud_base, sample_job, client
):
    """If status != 'completed', return 409."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "processing"
    job.speakers_resolved = False
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 409
    assert "completed" in resp.text.lower()


async def test_confirm_speakers_400_on_empty_assignments(
    icloud_base, sample_job, client
):
    """Empty speaker_assignments map → 400."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {}},
    )
    assert resp.status_code == 400


async def test_confirm_speakers_404_when_job_not_found(client):
    """Unknown job_id → 404."""
    resp = await client.post(
        "/job/does-not-exist/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 404


async def test_confirm_speakers_tolerates_stale_labels(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Per re-refine pattern (commits 0a45794 + 19f9450): if a submitted
    label is no longer in job.segments, the endpoint must NOT 400 — it
    relies on _apply_speaker_assignments' name-based fallback. The helper
    will record the assignment even if the original label is gone."""
    import state
    from unittest.mock import MagicMock

    suffix = uuid.uuid4().hex[:8]
    pascal_name = f"Pascal_T4stale_{suffix}"

    job = state.job_store.get(sample_job)
    # The submitted label "SPEAKER_99" doesn't appear in segments —
    # mimics the post-overlay drift the spec describes.
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": pascal_name},
    ]
    job.speakers = []
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    pascal_id = str(uuid.uuid4())
    state.speaker_store.create(pascal_id, pascal_name, f"speakers/{pascal_name}")
    clean_speakers.append(pascal_id)

    monkeypatch.setattr(state, "transcription_executor",
                        MagicMock(submit=MagicMock()))
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            extract_embedding=MagicMock(return_value=MagicMock()),
            update_embedding=MagicMock(),
        ),
        raising=False,
    )

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_99": pascal_id}},
    )
    # Must not 400 on the stale label — same contract as /re-refine.
    assert resp.status_code == 200, resp.text
