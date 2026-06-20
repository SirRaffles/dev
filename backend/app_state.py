"""Typed accessor façade over the shared `state.py` globals.

Each accessor reads through to the corresponding `state` module global at call
time (never snapshots at import), so existing tests that monkeypatch `state.*`
keep working. `state.py` remains the implementation; this is only a typed seam
for route code to read shared application state.
"""

import state


def jobs():
    """The primary JobStore (a.k.a. ``state.job_store`` / legacy ``state.jobs``)."""
    return state.job_store


def batch_jobs():
    return state.batch_jobs


def multimodal_jobs():
    return state.multimodal_jobs


def speaker_store():
    return state.speaker_store


def call_speaker_store():
    return state.call_speaker_store


def call_metadata_store():
    return state.call_metadata_store


def refinement_store():
    return state.refinement_store


def refinement_service():
    return state.refinement_service


def deliverable_service():
    return state.deliverable_service


def executor():
    return state.transcription_executor


def speaker_embedding_service():
    return state.get_speaker_embedding_service()


def is_ready_to_transcribe():
    return bool(state.whisper_model_ready and state.diarization_pipeline)


def refinement_available():
    return bool(state.refinement_available)


def deliverable_available():
    return bool(state.deliverable_available)


def startup_time():
    return state.startup_time
