"""B7 unit tests: learning system core helpers."""

import importlib
import json
from pathlib import Path


def _reload_learning():
    """Reload services.learning AND services.glossary so both pick up the
    icloud_base fixture's monkeypatched ICLOUD_BASE_PATH. Both modules bind
    the path at import time (LEARNING_LOG_PATH, GLOBAL_GLOSSARY_PATH)."""
    import services.glossary
    importlib.reload(services.glossary)
    import services.learning
    return importlib.reload(services.learning)


def test_record_event_appends_jsonl_line(icloud_base):
    learning = _reload_learning()
    learning.record_event("embedding_update", job_id="j-1",
                          speaker_id="s-1", speaker_name="Pascal", duration_sec=120.5)

    log = (icloud_base / "learning_log.jsonl")
    assert log.exists()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["type"] == "embedding_update"
    assert record["job_id"] == "j-1"
    assert record["speaker_id"] == "s-1"
    assert record["speaker_name"] == "Pascal"
    assert record["duration_sec"] == 120.5
    assert "ts" in record  # ISO timestamp


def test_record_event_timestamp_is_iso_z(icloud_base):
    learning = _reload_learning()
    learning.record_event("glossary_add", term="Manukai", job_id="j-2", confidence="high")
    line = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8").strip()
    record = json.loads(line)
    ts = record["ts"]
    # YYYY-MM-DDThh:mm:ssZ format (UTC, second precision)
    assert ts.endswith("Z")
    assert "T" in ts
    assert len(ts) == 20  # "2026-05-15T13:51:39Z"


def test_record_event_appends_multiple_lines(icloud_base):
    learning = _reload_learning()
    for i in range(3):
        learning.record_event("insight_added", job_id=f"j-{i}",
                              speaker_id="s-1", category="explicit", count=i)
    lines = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert [json.loads(l)["job_id"] for l in lines] == ["j-0", "j-1", "j-2"]


def test_record_event_never_raises_on_io_error(icloud_base, monkeypatch):
    """If the JSONL file is unwriteable (e.g. permissions), record_event must swallow."""
    learning = _reload_learning()
    # Patch open to raise OSError
    real_open = open
    def fake_open(path, *args, **kwargs):
        if str(path).endswith("learning_log.jsonl"):
            raise PermissionError("simulated")
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr("builtins.open", fake_open)
    # Must not raise
    learning.record_event("embedding_update", job_id="j-x", speaker_name="X")


def test_record_event_concurrent_writes_preserve_all_lines(icloud_base):
    """Two concurrent recorders both land their lines without truncation."""
    import threading
    learning = _reload_learning()

    def worker(label, n):
        for i in range(n):
            learning.record_event("embedding_update", job_id=f"{label}-{i}",
                                  speaker_name=label, duration_sec=10.0)

    t1 = threading.Thread(target=worker, args=("A", 10))
    t2 = threading.Thread(target=worker, args=("B", 10))
    t1.start(); t2.start(); t1.join(); t2.join()

    lines = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    # No truncated / merged lines: every line must parse as valid JSON
    for line in lines:
        json.loads(line)


def test_update_speaker_embeddings_skips_when_audio_missing(icloud_base):
    """No audio = no embedding work; emit a skipped event."""
    learning = _reload_learning()
    assignments = {"SPEAKER_00": "Pascal"}
    speaker_turns = [{"start": 0.0, "end": 120.0, "speaker": "SPEAKER_00"}]

    n = learning.update_speaker_embeddings(
        job_id="j-skip", audio_path=None,
        speaker_turns=speaker_turns, assignments=assignments,
    )
    assert n == 0
    log = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8")
    assert "embedding_skipped" in log
    assert "audio_unavailable" in log


def test_update_speaker_embeddings_skips_short_speakers(icloud_base, tmp_path, monkeypatch):
    """Speakers with < 60s of speech (sum of turn durations) are skipped."""
    learning = _reload_learning()
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"\x00" * 1024)

    from unittest.mock import MagicMock
    fake_emb_service = MagicMock(
        extract_speaker_embeddings=MagicMock(return_value={}),
        update_embedding=MagicMock(),
    )
    import state
    monkeypatch.setattr(state, "get_speaker_embedding_service",
                        lambda: fake_emb_service, raising=False)

    # SPEAKER_00 only has 30s of speech — below threshold
    speaker_turns = [
        {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00"},
        {"start": 20.0, "end": 40.0, "speaker": "SPEAKER_00"},
    ]
    assignments = {"SPEAKER_00": "Pascal"}

    n = learning.update_speaker_embeddings(
        job_id="j-short", audio_path=str(fake_audio),
        speaker_turns=speaker_turns, assignments=assignments,
    )
    assert n == 0
    # extract_speaker_embeddings should never be called (filtered out beforehand)
    fake_emb_service.extract_speaker_embeddings.assert_not_called()


def test_update_speaker_embeddings_merges_named_speakers(icloud_base, tmp_path, monkeypatch):
    """Named speaker with ≥60s of speech: extract fresh embedding + EMA merge."""
    import numpy as np
    from unittest.mock import MagicMock

    learning = _reload_learning()
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"\x00" * 1024)

    fresh_emb = np.ones(512, dtype=np.float32) / np.sqrt(512)
    fake_emb_service = MagicMock(
        extract_speaker_embeddings=MagicMock(return_value={"SPEAKER_00": fresh_emb}),
        update_embedding=MagicMock(),
    )
    fake_store = MagicMock(
        get_by_name=MagicMock(return_value={"speaker_id": "sp-pascal", "name": "Pascal"}),
    )
    import state
    monkeypatch.setattr(state, "get_speaker_embedding_service",
                        lambda: fake_emb_service, raising=False)
    monkeypatch.setattr(state, "speaker_store", fake_store)

    # 120s of Pascal speech (above threshold)
    speaker_turns = [
        {"start": 0.0, "end": 60.0, "speaker": "SPEAKER_00"},
        {"start": 100.0, "end": 160.0, "speaker": "SPEAKER_00"},
    ]
    assignments = {"SPEAKER_00": "Pascal"}

    n = learning.update_speaker_embeddings(
        job_id="j-merge", audio_path=str(fake_audio),
        speaker_turns=speaker_turns, assignments=assignments,
    )
    assert n == 1
    fake_emb_service.update_embedding.assert_called_once()
    call = fake_emb_service.update_embedding.call_args
    assert call.args[0] == "Pascal"  # name
    # alpha=0.3 default (positional or keyword)
    alpha = call.kwargs.get("alpha", call.args[2] if len(call.args) >= 3 else None)
    assert alpha == 0.3

    log = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8")
    assert "embedding_update" in log
    assert "Pascal" in log


def test_update_speaker_embeddings_skips_anonymous_labels(icloud_base, tmp_path, monkeypatch):
    """SPEAKER_XX labels (not in assignments) are ignored."""
    from unittest.mock import MagicMock

    learning = _reload_learning()
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"\x00" * 1024)

    fake_emb_service = MagicMock(extract_speaker_embeddings=MagicMock(return_value={}),
                                 update_embedding=MagicMock())
    import state
    monkeypatch.setattr(state, "get_speaker_embedding_service",
                        lambda: fake_emb_service, raising=False)

    # Two anonymous speakers, neither in assignments
    speaker_turns = [
        {"start": 0.0, "end": 120.0, "speaker": "SPEAKER_00"},
        {"start": 120.0, "end": 240.0, "speaker": "SPEAKER_01"},
    ]
    assignments = {}  # nothing named

    n = learning.update_speaker_embeddings(
        job_id="j-anon", audio_path=str(fake_audio),
        speaker_turns=speaker_turns, assignments=assignments,
    )
    assert n == 0
    fake_emb_service.update_embedding.assert_not_called()


def test_extract_insights_auto_returns_count_and_logs_events(icloud_base, monkeypatch):
    """Wraps _extract_speaker_insights_sync; one event per updated insight."""
    learning = _reload_learning()

    fake_result = {
        "updated": ["Pascal:explicit", "Pascal:implicit", "David:explicit"],
        "skipped": [],
        "errors": [],
    }
    # Patch the existing extraction function in its real module
    monkeypatch.setattr(
        "routes.transcription._extract_speaker_insights_sync",
        lambda job_id: fake_result,
    )

    n = learning.extract_insights_auto(job_id="j-ins-1")
    assert n == 3

    log_lines = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8").splitlines()
    insight_events = [json.loads(l) for l in log_lines if "insight_added" in l]
    assert len(insight_events) == 3
    speakers = {e["speaker_name"] for e in insight_events}
    assert speakers == {"Pascal", "David"}
    categories = {e["category"] for e in insight_events}
    assert categories == {"explicit", "implicit"}


def test_extract_insights_auto_returns_zero_on_no_updates(icloud_base, monkeypatch):
    learning = _reload_learning()
    monkeypatch.setattr(
        "routes.transcription._extract_speaker_insights_sync",
        lambda job_id: {"updated": [], "skipped": [{"speaker": "X", "reason": "no lines"}],
                         "errors": []},
    )
    n = learning.extract_insights_auto(job_id="j-ins-empty")
    assert n == 0


def test_extract_insights_auto_handles_helper_exception(icloud_base, monkeypatch):
    """Bubbles a single failure event but does not raise."""
    learning = _reload_learning()
    def boom(job_id):
        raise RuntimeError("claude unreachable")
    monkeypatch.setattr("routes.transcription._extract_speaker_insights_sync", boom)

    n = learning.extract_insights_auto(job_id="j-ins-boom")
    assert n == 0
    log = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8")
    assert "insight_failed" in log
