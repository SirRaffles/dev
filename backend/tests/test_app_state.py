import state
import app_state


def test_jobs_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "jobs", sentinel)
    assert app_state.jobs() is sentinel


def test_job_store_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "job_store", sentinel)
    assert app_state.job_store() is sentinel


def test_jobs_and_job_store_are_independent(monkeypatch):
    """state.jobs (alias) and state.job_store rebind independently under
    monkeypatch — the façade must NOT collapse them onto one global."""
    jobs_sentinel = object()
    store_sentinel = object()
    monkeypatch.setattr(state, "jobs", jobs_sentinel)
    monkeypatch.setattr(state, "job_store", store_sentinel)
    assert app_state.jobs() is jobs_sentinel
    assert app_state.job_store() is store_sentinel


def test_batch_jobs_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "batch_jobs", sentinel)
    assert app_state.batch_jobs() is sentinel


def test_multimodal_jobs_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "multimodal_jobs", sentinel)
    assert app_state.multimodal_jobs() is sentinel


def test_speaker_store_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "speaker_store", sentinel)
    assert app_state.speaker_store() is sentinel


def test_call_speaker_store_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "call_speaker_store", sentinel)
    assert app_state.call_speaker_store() is sentinel


def test_call_metadata_store_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "call_metadata_store", sentinel)
    assert app_state.call_metadata_store() is sentinel


def test_refinement_store_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "refinement_store", sentinel)
    assert app_state.refinement_store() is sentinel


def test_refinement_service_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "refinement_service", sentinel)
    assert app_state.refinement_service() is sentinel


def test_deliverable_service_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "deliverable_service", sentinel)
    assert app_state.deliverable_service() is sentinel


def test_executor_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "transcription_executor", sentinel)
    assert app_state.executor() is sentinel


def test_speaker_embedding_service_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "get_speaker_embedding_service", lambda: sentinel)
    assert app_state.speaker_embedding_service() is sentinel


def test_is_ready_combines_flags(monkeypatch):
    monkeypatch.setattr(state, "whisper_model_ready", True)
    monkeypatch.setattr(state, "diarization_pipeline", object())
    assert app_state.is_ready_to_transcribe() is True
    monkeypatch.setattr(state, "whisper_model_ready", False)
    assert app_state.is_ready_to_transcribe() is False


def test_is_ready_false_when_no_pipeline(monkeypatch):
    monkeypatch.setattr(state, "whisper_model_ready", True)
    monkeypatch.setattr(state, "diarization_pipeline", None)
    assert app_state.is_ready_to_transcribe() is False


def test_refinement_available_reads_through(monkeypatch):
    monkeypatch.setattr(state, "refinement_available", True)
    assert app_state.refinement_available() is True
    monkeypatch.setattr(state, "refinement_available", False)
    assert app_state.refinement_available() is False


def test_deliverable_available_reads_through(monkeypatch):
    monkeypatch.setattr(state, "deliverable_available", True)
    assert app_state.deliverable_available() is True
    monkeypatch.setattr(state, "deliverable_available", False)
    assert app_state.deliverable_available() is False


def test_startup_time_reads_through(monkeypatch):
    sentinel = 12345.6
    monkeypatch.setattr(state, "startup_time", sentinel)
    assert app_state.startup_time() == sentinel
