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
