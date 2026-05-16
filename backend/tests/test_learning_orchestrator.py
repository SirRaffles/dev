"""B7 orchestrator integration test."""

from unittest.mock import MagicMock, patch


def test_run_post_refinement_learning_aggregates_status_ok(icloud_base, monkeypatch, tmp_path):
    """All three workers succeed → learning_status='ok', counts in summary."""
    from job_models import TranscriptionJob
    from routes import refinement as rmodule

    job = TranscriptionJob("job-L1")
    import state
    monkeypatch.setattr(state, "jobs", MagicMock(get=MagicMock(return_value=job),
                                                  update=MagicMock()))

    fake_audio = tmp_path / "fake.wav"
    fake_audio.write_bytes(b"\x00" * 1024)

    segments = [
        {"start": 0, "end": 60, "speaker": "Pascal", "text": "..."},
        {"start": 60, "end": 120, "speaker": "Pascal", "text": "..."},
        {"start": 120, "end": 180, "speaker": "David", "text": "..."},
        {"start": 180, "end": 200, "speaker": "SPEAKER_02", "text": "..."},
    ]
    analysis = {
        "corrections": [{"original": "Stara", "corrected": "Starrag", "confidence": "high"}],
    }

    # Patch each worker to return a known count
    monkeypatch.setattr("services.learning.update_speaker_embeddings",
                        lambda **kwargs: 2)
    monkeypatch.setattr("services.learning.extract_insights_auto",
                        lambda **kwargs: 4)
    monkeypatch.setattr("services.learning.learn_glossary_terms",
                        lambda **kwargs: 1)

    rmodule._run_post_refinement_learning(
        job_id="job-L1", audio_path=str(fake_audio),
        segments=segments, analysis=analysis,
    )

    assert job.learning_status == "ok"
    assert job.learning_summary == {
        "embeddings_updated": 2,
        "insights_added": 4,
        "terms_learned": 1,
    }


def test_run_post_refinement_learning_partial_when_one_worker_fails(icloud_base, tmp_path, monkeypatch):
    """One worker raises → learning_status='partial'; others' counts still recorded."""
    from job_models import TranscriptionJob
    from routes import refinement as rmodule

    job = TranscriptionJob("job-L2")
    import state
    monkeypatch.setattr(state, "jobs", MagicMock(get=MagicMock(return_value=job),
                                                  update=MagicMock()))

    fake_audio = tmp_path / "fake.wav"
    fake_audio.write_bytes(b"\x00" * 1024)

    def boom(**kwargs): raise RuntimeError("boom")
    monkeypatch.setattr("services.learning.update_speaker_embeddings", boom)
    monkeypatch.setattr("services.learning.extract_insights_auto", lambda **kwargs: 3)
    monkeypatch.setattr("services.learning.learn_glossary_terms", lambda **kwargs: 2)

    rmodule._run_post_refinement_learning(
        job_id="job-L2", audio_path=str(fake_audio),
        segments=[], analysis={"corrections": []},
    )

    assert job.learning_status == "partial"
    assert job.learning_summary["embeddings_updated"] == 0
    assert job.learning_summary["insights_added"] == 3
    assert job.learning_summary["terms_learned"] == 2


def test_run_post_refinement_learning_failed_when_all_fail(tmp_path, monkeypatch):
    from job_models import TranscriptionJob
    from routes import refinement as rmodule

    job = TranscriptionJob("job-L3")
    import state
    monkeypatch.setattr(state, "jobs", MagicMock(get=MagicMock(return_value=job),
                                                  update=MagicMock()))

    def boom(**kwargs): raise RuntimeError("boom")
    monkeypatch.setattr("services.learning.update_speaker_embeddings", boom)
    monkeypatch.setattr("services.learning.extract_insights_auto", boom)
    monkeypatch.setattr("services.learning.learn_glossary_terms", boom)

    rmodule._run_post_refinement_learning(
        job_id="job-L3", audio_path=None, segments=[], analysis={},
    )
    assert job.learning_status == "failed"
    assert job.learning_summary == {
        "embeddings_updated": 0, "insights_added": 0, "terms_learned": 0,
    }


def test_assignments_map_excludes_anonymous_labels(tmp_path, monkeypatch, icloud_base):
    """The assignments dict passed to update_speaker_embeddings must omit SPEAKER_XX labels."""
    from job_models import TranscriptionJob
    from routes import refinement as rmodule

    job = TranscriptionJob("job-L4")
    import state
    monkeypatch.setattr(state, "jobs", MagicMock(get=MagicMock(return_value=job),
                                                  update=MagicMock()))

    captured = {}
    def capture_emb(**kwargs):
        captured["assignments"] = kwargs.get("assignments")
        return 0
    monkeypatch.setattr("services.learning.update_speaker_embeddings", capture_emb)
    monkeypatch.setattr("services.learning.extract_insights_auto", lambda **kwargs: 0)
    monkeypatch.setattr("services.learning.learn_glossary_terms", lambda **kwargs: 0)

    segments = [
        {"start": 0, "end": 60, "speaker": "Pascal"},
        {"start": 60, "end": 120, "speaker": "SPEAKER_01"},
        {"start": 120, "end": 180, "speaker": "David"},
    ]
    rmodule._run_post_refinement_learning(
        job_id="job-L4", audio_path=None, segments=segments, analysis={},
    )
    assignments = captured["assignments"]
    assert "SPEAKER_01" not in assignments
    assert "Pascal" in assignments.values()
    assert "David" in assignments.values()
