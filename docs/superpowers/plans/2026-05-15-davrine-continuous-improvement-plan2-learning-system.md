# Davrine Continuous Improvement — Plan 2 (Learning System B7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the B7 continuous-learning layer: after each refined transcription, run three failure-isolated workers (embedding update, insight extraction, glossary learning) and append structured events to an append-only `learning_log.jsonl` on iCloud. Surface a `GET /learning/log` endpoint for the future B6e Activity timeline.

**Architecture:** A new `backend/services/learning.py` houses 4 pure functions: `record_event` (fcntl-locked JSONL append), `update_speaker_embeddings` (EMA-merge fresh embeddings into the registry for any named speaker with ≥60s of speech), `extract_insights_auto` (in-process call to the existing insight-extraction logic), `learn_glossary_terms` (append high-confidence corrections to `_global.md` via the Task 2 helper). An orchestrator `_run_post_refinement_learning` is invoked at the tail of `_run_refinement_for_job` in `backend/routes/refinement.py`, after corrections have been applied. Each worker's exception is caught locally; status rolls up to `learning_status: ok | partial | failed` on the job. New `backend/routes/learning.py` exposes `GET /learning/log?since=...&type=...&limit=...` for the activity timeline (Plan 3).

**Tech Stack:** Python 3.11+ stdlib (`fcntl`, `json`, `unicodedata`, `datetime`), FastAPI, pyannote-audio (already wired via existing `SpeakerEmbeddingService`), Claude CLI (via existing `DeliverableService`).

---

## File Structure

**Create:**
- `backend/services/learning.py` — `record_event` + 3 workers
- `backend/tests/test_learning.py` — unit tests for the 4 functions
- `backend/tests/test_learning_orchestrator.py` — integration test for `_run_post_refinement_learning`
- `backend/routes/learning.py` — `GET /learning/log` endpoint
- `backend/tests/test_learning_log_route.py` — endpoint tests

**Modify:**
- `backend/routes/refinement.py` — extend `_run_refinement_for_job` signature with `audio_path: Optional[str] = None`; call `_run_post_refinement_learning` at the tail of the success branch
- `backend/services/transcription.py` — auto-dispatch passes `audio_path` (the original, un-trimmed audio path) through to `_run_refinement_for_job`. **Also delay tmp-audio cleanup** when auto-refine is dispatched, since the learning workers need to read the audio (without this, the cleanup `finally` in `_run_transcription_sync` deletes the tmp file before the executor picks up refinement → embedding worker skips silently)
- `backend/main.py` — `app.include_router(learning_router, dependencies=_rate_dep)` after the existing routers

**Reference (read-only):**
- `backend/services/glossary.py` — already ships `append_auto_learned_term` (Plan 1 Task 2)
- `backend/services/speaker_embedding.py:235-321` — `register_speaker`, `update_embedding(name, embedding, alpha=0.3)`; `extract_speaker_embeddings(audio_path, speaker_turns) -> Dict[str, np.ndarray]`
- `backend/routes/transcription.py:957-1023` — `_extract_speaker_insights_sync(job_id) -> dict` (existing manual insight extraction; we'll reuse it directly)
- `backend/routes/transcription.py:924-954` — `_resolve_job_audio_path(job_id)` (best-effort post-cleanup audio resolution for JPR uploads)
- `backend/job_models.py:33-36` — `learning_summary`, `learning_status` fields (Plan 1 Task 6 added them)
- `backend/routes/refinement.py:34-92` — `_run_refinement_for_job` (Plan 1 Task 7 helper)

---

## Conventions

- Run pytest as `cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q` (or `-v` for verbose).
- Branch: `dev`. Push at the end of Task 9, after the Pascal Weber re-validation passes.
- **Commit hygiene:** WIP files exist on `dev` (~22 files outside Plan scope). Always `git add <specific files>` — never `git add -A`. Use stash-dance (`git stash push --keep-index --include-untracked -- <file>`) if your task collides with WIP on the same file.
- TDD: write failing tests first, watch them fail, then implement. Reference superpowers:test-driven-development.
- Each task ends with one commit (the implementer subagent will follow this).

---

## Task 1: Baseline & branch check

**Files:**
- None (verification only)

- [ ] **Step 1: Confirm we're on `dev`, up to date with origin**

```bash
cd ~/Development/apps/whisper-transcription-app && git status -sb | head -3
```
Expected: `## dev...origin/dev` (working tree may have WIP).

- [ ] **Step 2: Baseline pytest count**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: `281 passed, 3 skipped` (post-Plan 1 baseline).

- [ ] **Step 3: Verify Plan 1 artifacts exist**

```bash
test -f ~/Development/apps/whisper-transcription-app/backend/services/glossary.py && \
test -f ~/Development/apps/whisper-transcription-app/backend/services/refinement.py && \
test -f ~/Development/apps/whisper-transcription-app/backend/routes/refinement.py && \
grep -q "_run_refinement_for_job" ~/Development/apps/whisper-transcription-app/backend/routes/refinement.py && \
echo "Plan 1 surfaces OK"
```

---

## Task 2: `learning.py` skeleton + `record_event` (fcntl-locked JSONL)

**Files:**
- Create: `backend/services/learning.py`
- Create: `backend/tests/test_learning.py`

The append-only `learning_log.jsonl` lives at `<ICLOUD_BASE_PATH>/learning_log.jsonl`. Use `fcntl.LOCK_EX` advisory lock during open+append+close, then `fsync()` before unlocking. iCloud has no transactional guarantees, so the locking is non-negotiable.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_learning.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v 2>&1 | tail -15
```
Expected: ImportError on `services.learning`.

- [ ] **Step 3: Implement `backend/services/learning.py`**

```python
"""Continuous learning system (B7).

After each refined transcription, three failure-isolated workers run:
- update_speaker_embeddings: EMA-merge fresh voice embeddings into the registry
- extract_insights_auto: refresh per-speaker insights from the new transcript
- learn_glossary_terms: surface high-confidence corrections as pending-review terms

Every action appends a structured event to learning_log.jsonl on iCloud (with
fcntl LOCK_EX + fsync for crash-safety across concurrent writers).
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)

LEARNING_LOG_PATH: Path = ICLOUD_BASE_PATH / "learning_log.jsonl"


def _utc_iso_z() -> str:
    """RFC 3339 / ISO 8601 UTC timestamp with second precision (e.g. 2026-05-15T13:51:39Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_event(event_type: str, **fields) -> None:
    """Append one JSON line to learning_log.jsonl on iCloud.

    Holds fcntl.LOCK_EX for the duration of write + fsync to serialize
    concurrent writers (iCloud has no atomic-append guarantees).

    Never raises — logs and returns on any IO/lock failure.
    """
    if not event_type:
        return
    record = {"ts": _utc_iso_z(), "type": event_type, **fields}
    payload = json.dumps(record, ensure_ascii=False) + "\n"

    try:
        LEARNING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEARNING_LOG_PATH, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
    except OSError as exc:
        logger.warning("learning: record_event(%s) failed: %s", event_type, exc)
```

- [ ] **Step 4: Run tests; verify all 5 pass**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v 2>&1 | tail -15
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/learning.py backend/tests/test_learning.py
git commit -m "B7: add learning.record_event JSONL appender with fcntl lock"
```

---

## Task 3: `update_speaker_embeddings` worker

**Files:**
- Modify: `backend/services/learning.py` — add the worker
- Modify: `backend/tests/test_learning.py` — add tests

For each pyannote label whose segment text now bears a registered speaker name (manual `speaker_ids` or B5 auto-match with `matched=True`), if total speaking duration is ≥ `MIN_LEARNING_DURATION_SEC` (60s default), extract a fresh embedding from the audio (using the existing `SpeakerEmbeddingService.extract_speaker_embeddings`) and merge into the registry via `embedding_service.update_embedding(name, emb, alpha=0.3)`. Returns count of speakers actually updated.

**Audio resolution:** the worker accepts `audio_path: Optional[str]`. If None or the file doesn't exist (direct-upload tmp deleted), log a `"embedding_skipped"` event with `reason="audio_unavailable"` and return 0 — the worker is best-effort.

- [ ] **Step 1: Append failing tests to `backend/tests/test_learning.py`**

```python
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
```

- [ ] **Step 2: Run tests; confirm they fail**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v -k "update_speaker_embeddings" 2>&1 | tail -10
```
Expected: AttributeError (function doesn't exist).

- [ ] **Step 3: Implement the worker in `services/learning.py`**

Add to the module (after `record_event`):

```python
MIN_LEARNING_DURATION_SEC = 60.0
EMA_ALPHA = 0.3


def update_speaker_embeddings(
    job_id: str,
    audio_path: Optional[str],
    speaker_turns: list,
    assignments: dict,
) -> int:
    """EMA-merge fresh voice embeddings for named speakers with ≥60s of speech.

    Args:
        job_id: For the learning_log event.
        audio_path: Path to the original audio file. None or missing → skip.
        speaker_turns: pyannote diarization [{start, end, speaker}, ...].
        assignments: {pyannote_label: speaker_name} for speakers we recognized
            (built by the orchestrator from refined segments).

    Returns: number of speakers whose embedding was updated.
    Never raises — caller wraps in try/except for the orchestrator's status rollup.
    """
    import state

    if not audio_path or not os.path.exists(audio_path):
        record_event("embedding_skipped", job_id=job_id, reason="audio_unavailable")
        return 0
    if not assignments:
        return 0

    # Build per-label total duration so we can filter short speakers BEFORE
    # paying for embedding extraction.
    duration_by_label: dict = {}
    for turn in speaker_turns:
        lbl = turn.get("speaker")
        if not lbl:
            continue
        duration_by_label[lbl] = duration_by_label.get(lbl, 0.0) + max(
            0.0, float(turn.get("end", 0)) - float(turn.get("start", 0))
        )

    eligible = {
        lbl: name for lbl, name in assignments.items()
        if duration_by_label.get(lbl, 0.0) >= MIN_LEARNING_DURATION_SEC
    }
    if not eligible:
        return 0

    # Only request embeddings for eligible labels (extract_speaker_embeddings
    # uses the longest turn internally, which is what we want here too).
    eligible_turns = [t for t in speaker_turns if t.get("speaker") in eligible]
    embedding_service = state.get_speaker_embedding_service()
    fresh = embedding_service.extract_speaker_embeddings(audio_path, eligible_turns)

    updated = 0
    for lbl, name in eligible.items():
        emb = fresh.get(lbl)
        if emb is None:
            continue
        try:
            embedding_service.update_embedding(name, emb, alpha=EMA_ALPHA)
            updated += 1
            speaker = None
            try:
                speaker = state.speaker_store.get_by_name(name)
            except Exception:
                pass
            record_event(
                "embedding_update",
                job_id=job_id,
                speaker_id=(speaker or {}).get("speaker_id"),
                speaker_name=name,
                duration_sec=round(duration_by_label.get(lbl, 0.0), 2),
                alpha=EMA_ALPHA,
            )
        except Exception:
            logger.exception("update_embedding failed for %s (job %s)", name, job_id)
            record_event("embedding_failed", job_id=job_id, speaker_name=name)
    return updated
```

- [ ] **Step 4: Run tests; verify all 4 pass**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v 2>&1 | tail -15
```
Expected: 9 passed (5 from Task 2 + 4 new).

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/learning.py backend/tests/test_learning.py
git commit -m "B7: update_speaker_embeddings worker with 60s threshold + EMA merge"
```

---

## Task 4: `extract_insights_auto` worker (in-process insight extraction)

**Files:**
- Modify: `backend/services/learning.py` — add the worker
- Modify: `backend/tests/test_learning.py` — add tests

The existing `_extract_speaker_insights_sync(job_id) -> dict` at `routes/transcription.py:957` already implements the full per-speaker insight extraction (explicit + implicit) using `state.deliverable_service`. The worker is a thin wrapper that calls it in-process (no HTTP), records a `"insight_added"` event for each `updated` entry, and returns the count of successfully updated insight files.

- [ ] **Step 1: Append failing tests**

```python
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
```

- [ ] **Step 2: Run tests; confirm they fail**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v -k "extract_insights_auto" 2>&1 | tail -10
```
Expected: AttributeError.

- [ ] **Step 3: Implement worker**

Add to `services/learning.py`:

```python
def extract_insights_auto(job_id: str) -> int:
    """Refresh explicit + implicit insights for every named speaker in the job's
    refined segments. Records one 'insight_added' event per (speaker, category).

    Returns the count of (speaker, category) pairs successfully updated.
    Never raises.
    """
    try:
        # Lazy import: routes module pulls in FastAPI heavy deps; defer until
        # the worker actually runs (not at services module load).
        from routes.transcription import _extract_speaker_insights_sync
        result = _extract_speaker_insights_sync(job_id)
    except Exception:
        logger.exception("extract_insights_auto failed for job %s", job_id)
        record_event("insight_failed", job_id=job_id)
        return 0

    updated = result.get("updated", []) if isinstance(result, dict) else []
    count = 0
    for entry in updated:
        # Entry shape: "Pascal:explicit" or "David:implicit"
        if ":" not in entry:
            continue
        speaker_name, category = entry.split(":", 1)
        record_event(
            "insight_added",
            job_id=job_id,
            speaker_name=speaker_name.strip(),
            category=category.strip(),
            count=1,
        )
        count += 1
    return count
```

- [ ] **Step 4: Run tests; verify 3 new pass**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v 2>&1 | tail -15
```
Expected: 12 passed (9 + 3).

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/learning.py backend/tests/test_learning.py
git commit -m "B7: extract_insights_auto worker (in-process reuse of existing extractor)"
```

---

## Task 5: `learn_glossary_terms` worker

**Files:**
- Modify: `backend/services/learning.py` — add the worker
- Modify: `backend/tests/test_learning.py` — add tests

For each refinement correction with `confidence == "high"`, check if the corrected term is already known (active or pending). If unknown, append to `_global.md` via the Plan 1 Task 2 helper `append_auto_learned_term`. Records one `"glossary_add"` event per term actually added.

The "already known" check is delegated to `glossary.append_auto_learned_term`'s built-in idempotency — we don't reimplement it. We just count the additions by reading the file before/after each call. (Simpler: count by checking whether the file grew. Simpler still: trust `append_auto_learned_term`'s idempotency and emit `glossary_add` only if a post-call recheck shows the term is now present — which it should be either way.)

**Cleaner approach:** call `_existing_normalized_terms` from `glossary.py` to compute the known set ourselves, then iterate corrections, only emit events for net-new terms, and finally call `append_auto_learned_term` for them. This gives us accurate event counts without re-reading the file.

- [ ] **Step 1: Append failing tests**

```python
def test_learn_glossary_terms_adds_high_confidence_only(icloud_base):
    """Only confidence='high' corrections become auto-learned terms."""
    learning = _reload_learning()

    corrections = [
        {"original": "Manuk AI", "corrected": "Manukai", "confidence": "high"},
        {"original": "Stara", "corrected": "Starrag", "confidence": "high"},
        {"original": "donie", "corrected": "Donny", "confidence": "medium"},  # filtered
        {"original": "uh", "corrected": "okay", "confidence": "low"},          # filtered
    ]
    n = learning.learn_glossary_terms(job_id="j-glo", corrections=corrections)
    assert n == 2

    glossary_path = icloud_base / "contexts" / "_global.md"
    body = glossary_path.read_text(encoding="utf-8")
    assert "Manukai" in body.split("## Auto-learned (pending review)")[1]
    assert "Starrag" in body.split("## Auto-learned (pending review)")[1]
    assert "Donny" not in body
    assert "okay" not in body

    log = (icloud_base / "learning_log.jsonl").read_text(encoding="utf-8")
    assert "Manukai" in log
    assert "Starrag" in log


def test_learn_glossary_terms_dedupe_against_active(icloud_base):
    """If a high-confidence correction already exists in Active, don't re-add."""
    (icloud_base / "contexts" / "_global.md").write_text(
        "# Global Glossary\n\n## Active\n\nManukai, DMG Mori\n",
        encoding="utf-8",
    )
    learning = _reload_learning()

    corrections = [
        {"original": "Manuk AI", "corrected": "Manukai", "confidence": "high"},  # already in Active
        {"original": "BMG Mori", "corrected": "DMG Mori", "confidence": "high"},  # already in Active
        {"original": "Stara", "corrected": "Starrag", "confidence": "high"},      # new
    ]
    n = learning.learn_glossary_terms(job_id="j-dedupe", corrections=corrections)
    assert n == 1  # only Starrag is genuinely new

    body = (icloud_base / "contexts" / "_global.md").read_text(encoding="utf-8")
    pending = body.split("## Auto-learned (pending review)")[1] if "## Auto-learned (pending review)" in body else ""
    assert "Starrag" in pending
    assert "- Manukai" not in pending  # not re-added as a pending bullet
    assert "- DMG Mori" not in pending


def test_learn_glossary_terms_empty_input(icloud_base):
    learning = _reload_learning()
    assert learning.learn_glossary_terms(job_id="j-empty", corrections=[]) == 0
    assert learning.learn_glossary_terms(job_id="j-none", corrections=None) == 0
```

- [ ] **Step 2: Run; verify failure**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v -k "learn_glossary" 2>&1 | tail -10
```

- [ ] **Step 3: Implement worker**

Add to `services/learning.py`:

```python
def learn_glossary_terms(job_id: str, corrections: Optional[list]) -> int:
    """Append high-confidence proper-noun corrections to _global.md.

    Only acts on `confidence='high'` corrections. Uses the glossary helper's
    idempotent normalization — terms already known anywhere in the file
    (active or pending) are skipped silently.

    Returns count of net-new terms added. Never raises.
    """
    if not corrections:
        return 0

    # Lazy import for two reasons: glossary imports from services.transcription
    # (the circular-load issue Plan 1 documents), and we want a fresh read of
    # the current normalized-terms set per call.
    from services.glossary import (
        append_auto_learned_term,
        load_global_glossary,
        _existing_normalized_terms,
        _normalize_term,
    )

    body = load_global_glossary() or ""
    known = _existing_normalized_terms(body)

    added = 0
    for c in corrections:
        if not isinstance(c, dict):
            continue
        if c.get("confidence") != "high":
            continue
        term = (c.get("corrected") or "").strip()
        if not term:
            continue
        norm = _normalize_term(term)
        if not norm or norm in known:
            continue
        try:
            append_auto_learned_term(
                term,
                source_job_id=job_id,
                context_phrase=(c.get("original") or "")[:120],
            )
        except Exception:
            logger.exception("append_auto_learned_term failed for %r", term)
            continue
        known.add(norm)  # avoid re-counting if the same term appears twice in corrections
        record_event(
            "glossary_add",
            job_id=job_id,
            term=term,
            source_phrase=c.get("original", ""),
            confidence="high",
        )
        added += 1
    return added
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning.py -v 2>&1 | tail -15
```
Expected: 15 passed (12 + 3).

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/learning.py backend/tests/test_learning.py
git commit -m "B7: learn_glossary_terms worker (dedupes against existing glossary)"
```

---

## Task 6: Orchestrator + wiring into `_run_refinement_for_job`

**Files:**
- Modify: `backend/routes/refinement.py`
  - Add module-level `_cleanup_deferred_audio(audio_path)` helper.
  - Add module-level `_run_post_refinement_learning(...)` orchestrator.
  - Extend `_run_refinement_for_job` signature with `audio_path: Optional[str] = None`; add `finally:` that calls `_cleanup_deferred_audio(audio_path)`; invoke orchestrator at the tail of the success branch.
  - **Update the existing `_run_refinement(job_id)` wrapper** to call `_resolve_job_audio_path(job_id)` (lazy import from `routes.transcription`) and forward the result as `audio_path`.
  - Add `import os`, `import shutil`, `import tempfile` at module top.
- Modify: `backend/services/transcription.py` — auto-dispatch passes `audio_path` through AND sets `job._defer_audio_cleanup = True`; outer `finally` block guards `audio_path` deletion behind that flag.
- Create: `backend/tests/test_learning_orchestrator.py`

The orchestrator runs 3 workers, each in its own try/except. Builds an assignments map from refined segments (any `seg["speaker"]` that doesn't start with `SPEAKER_` is a recognized name). Sets `learning_summary` and `learning_status` on the job, then persists via `state.jobs.update`.

**Cleanup deferral:** the current `_run_transcription_sync` `finally` block deletes `audio_path` and its tmp parent dir. When B7 needs that audio for embedding extraction, we must keep it alive. Approach:
- In auto-dispatch, set `job._defer_cleanup = True` and pass `audio_path` to `_run_refinement_for_job`.
- The orchestrator finally-block (after learning workers complete) does the cleanup that `_run_transcription_sync` skipped.

- [ ] **Step 1: Write orchestrator test**

Create `backend/tests/test_learning_orchestrator.py`:

```python
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
    # Speaker name → label is also in there? Spec says {pyannote_label: speaker_name},
    # but for refined segments we only know the name, so use name as both key and value.
    assert "Pascal" in assignments.values()
    assert "David" in assignments.values()
```

- [ ] **Step 2: Run; confirm failure**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_orchestrator.py -v 2>&1 | tail -15
```
Expected: AttributeError on `_run_post_refinement_learning`.

- [ ] **Step 3: Implement orchestrator in `backend/routes/refinement.py`**

Add the orchestrator (at module level, near `_run_refinement_for_job`):

```python
def _run_post_refinement_learning(job_id: str, audio_path: Optional[str],
                                  segments: list, analysis: dict) -> None:
    """B7 orchestrator: run the three learning workers, aggregate status.

    Each worker is wrapped in its own try/except — one failure must not block
    the others. Sets job.learning_summary + job.learning_status, then persists
    via state.jobs.update.
    """
    from services import learning

    # Build {pyannote_label_or_name: speaker_name} from refined segments.
    # After refinement, segments use real speaker names instead of SPEAKER_XX
    # (or keep SPEAKER_XX if neither B5 nor refinement could identify them).
    assignments: dict = {}
    for seg in (segments or []):
        spk = (seg.get("speaker") or "").strip()
        if not spk or spk.startswith("SPEAKER_"):
            continue
        assignments[spk] = spk  # key=name, value=name (we no longer have the original label)

    # Prefer pyannote's raw turn boundaries (higher precision: 30s+ continuous
    # speech blocks) over per-utterance segments (3-10s each). Both B5 and the
    # diarization step populate job.speakers with pyannote-shaped turns; fall
    # back to synthesizing from refined segments only if job.speakers is empty.
    job_for_turns = state.jobs.get(job_id)
    raw_turns = (job_for_turns.speakers if job_for_turns is not None else None) or []
    if raw_turns:
        # Map labels post-overlay: B5 may have rewritten "SPEAKER_00" → "Pascal"
        # in BOTH segments and job.speakers (Plan 1 Task 9 follow-up commit).
        speaker_turns = [
            {"start": float(t.get("start", 0)),
             "end": float(t.get("end", 0)),
             "speaker": t.get("speaker", "")}
            for t in raw_turns
            if (t.get("speaker") or "").strip()
        ]
    else:
        speaker_turns = [
            {"start": float(seg.get("start", 0)),
             "end": float(seg.get("end", 0)),
             "speaker": seg.get("speaker", "")}
            for seg in (segments or [])
            if (seg.get("speaker") or "").strip()
        ]

    successes = 0
    emb_count = ins_count = glo_count = 0

    try:
        emb_count = learning.update_speaker_embeddings(
            job_id=job_id, audio_path=audio_path,
            speaker_turns=speaker_turns, assignments=assignments,
        )
        successes += 1
    except Exception:
        logger.exception("B7 embedding worker failed for job %s", job_id)

    try:
        ins_count = learning.extract_insights_auto(job_id=job_id)
        successes += 1
    except Exception:
        logger.exception("B7 insight worker failed for job %s", job_id)

    try:
        glo_count = learning.learn_glossary_terms(
            job_id=job_id, corrections=(analysis or {}).get("corrections", []),
        )
        successes += 1
    except Exception:
        logger.exception("B7 glossary worker failed for job %s", job_id)

    # Use state.jobs (same convention as _run_transcription_sync). state.job_store
    # is an alias bound at module load, but monkeypatching one in tests does NOT
    # update the other — so be consistent with the writer-side convention.
    job = state.jobs.get(job_id)
    if job is not None:
        job.learning_summary = {
            "embeddings_updated": emb_count,
            "insights_added": ins_count,
            "terms_learned": glo_count,
        }
        if successes == 3:
            job.learning_status = "ok"
        elif successes >= 1:
            job.learning_status = "partial"
        else:
            job.learning_status = "failed"
        try:
            state.jobs.update(job)
        except Exception:
            logger.debug("jobs.update mirror failed for job %s", job_id, exc_info=True)
```

Then extend `_run_refinement_for_job` to accept `audio_path` and invoke the orchestrator at the tail of the success branch (right after `state.refinement_store.save_result(job_id, result)` and `_set_refinement_status(job, "done")`):

```python
def _run_refinement_for_job(job_id: str, speaker_ids: Optional[List[str]] = None,
                            context_path: Optional[str] = None,
                            audio_path: Optional[str] = None):
    # ... existing body (job-fetch, status="processing", precondition checks,
    #     context loading, refine call) unchanged ...
    try:
        # ... existing try body up to the success branch ...
        result = state.refinement_service.refine(
            job.segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
        )
        state.refinement_store.save_result(job_id, result)
        _set_refinement_status(job, "done")
        logger.info("Refinement complete for job %s", job_id)

        # B7: post-refinement learning. Best-effort — never raises.
        try:
            _run_post_refinement_learning(
                job_id=job_id,
                audio_path=audio_path,
                segments=result.get("refined_segments", job.segments),
                analysis=result.get("analysis", {}),
            )
        except Exception:
            logger.exception("B7 orchestrator outer failure for job %s", job_id)

    except Exception as e:
        # existing failure path — log, mark failed, swallow
        logger.exception("Refinement failed for job %s", job_id)
        state.refinement_store.update_status(job_id, "failed", str(e))
        _set_refinement_status(job, "failed")
    finally:
        # B7 deferred cleanup: _run_transcription_sync skipped tmp-audio cleanup
        # when it dispatched us (job._defer_audio_cleanup=True). We own the
        # cleanup now — runs on success path, refine-failure path, and
        # orchestrator-failure path alike. If audio_path is None (manual route,
        # or audio already gone), this is a no-op.
        _cleanup_deferred_audio(audio_path)
```

Also add the cleanup helper at module top (after `_set_refinement_status`):

```python
def _cleanup_deferred_audio(audio_path: Optional[str]) -> None:
    """Delete the tmp audio file (and its tmp parent dir) that
    _run_transcription_sync deferred to us. No-op when audio_path is None,
    when the path is gone, or when it's outside /tmp."""
    if not audio_path:
        return
    try:
        parent_dir = os.path.dirname(audio_path)
        if parent_dir and os.path.isdir(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(parent_dir, ignore_errors=True)
        elif os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        logger.debug("B7 audio cleanup failed for %s", audio_path, exc_info=True)
```

Add at the top of `routes/refinement.py` (with the other module imports):

```python
import os
import shutil
import tempfile
```

**Note:** the orchestrator code above intentionally contains NO cleanup logic — that lives in `_run_refinement_for_job`'s `finally` block (added earlier in this step). Single owner → fires on every path (success / refine-failure / orchestrator-failure).

Update the backward-compat wrapper to resolve audio via the existing helper:

```python
def _run_refinement(job_id: str):
    """Backwards-compatible wrapper: manual route resolves audio for B7."""
    # Lazy import to avoid pulling routes.transcription at module load.
    try:
        from routes.transcription import _resolve_job_audio_path
        audio_path = _resolve_job_audio_path(job_id)
    except Exception:
        audio_path = None
    _run_refinement_for_job(job_id, speaker_ids=None, context_path=None,
                            audio_path=audio_path)
```

- [ ] **Step 4: Update auto-dispatch in `services/transcription.py`**

Find the B2 dispatch block (around line 835-865 — Plan 1 Task 8). Currently:

```python
state.transcription_executor.submit(
    _run_refinement_for_job,
    job_id,
    settings.speaker_ids,
    settings.context_path,
)
```

Change to pass `audio_path`:

```python
state.transcription_executor.submit(
    _run_refinement_for_job,
    job_id,
    settings.speaker_ids,
    settings.context_path,
    audio_path,
)
```

Also mark the job so the outer `finally` skips cleanup (the learning worker needs the audio). Add right before the `submit` call:

```python
job._defer_audio_cleanup = True
```

And in the outer `finally` block of `_run_transcription_sync` (around line 819-848), guard the audio cleanup:

```python
finally:
    try:
        if 'trimmed_temp_path' in locals() and trimmed_temp_path and os.path.exists(trimmed_temp_path):
            os.remove(trimmed_temp_path)
    except Exception:
        pass
    retry_of = getattr(job, "_retry_of", None) if job is not None else None
    if retry_of:
        return
    # B7: if auto-refine was dispatched, the learning workers need the audio.
    # _run_refinement_for_job's finally block will call _cleanup_deferred_audio
    # once refinement + learning (or any failure path) completes.
    if getattr(job, "_defer_audio_cleanup", False):
        return
    try:
        parent_dir = os.path.dirname(audio_path)
        if parent_dir and os.path.isdir(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(parent_dir, ignore_errors=True)
        elif os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        pass
```

**Audio cleanup ownership:** the orchestrator does NOT clean up tmp audio. That responsibility lives in `_run_refinement_for_job`'s `finally` (added in Step 3 above) so it fires on success path, refinement-failure path, AND orchestrator-failure path. Single owner → no leaks.

- [ ] **Step 5: Run orchestrator tests**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_orchestrator.py -v 2>&1 | tail -15
```
Expected: 4 passed.

- [ ] **Step 6: Run full backend suite for regressions**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: 300 passed (281 + 15 learning + 4 orchestrator), 3 skipped.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/refinement.py backend/services/transcription.py backend/tests/test_learning_orchestrator.py
git commit -m "B7: orchestrate learning workers post-refinement + defer tmp cleanup"
```

---

## Task 7: `GET /learning/log` endpoint

**Files:**
- Create: `backend/routes/learning.py`
- Create: `backend/tests/test_learning_log_route.py`
- Modify: `backend/main.py` — register the router

The endpoint reads `learning_log.jsonl` line-by-line (small file, hundreds of bytes per line, expected to stay under 10MB for the next year). Filters by `since` (ISO timestamp string comparison works because timestamps are zero-padded UTC) and `type`. Pagination via `limit` (default 100, max 500) and `offset`.

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_learning_log_route.py`:

```python
"""B7 endpoint tests: GET /learning/log."""

import importlib
import json
import pytest


def _seed_log(icloud_base, entries):
    """Seed the log file AND reload services.learning so the endpoint
    reads the patched ICLOUD_BASE_PATH (constant is captured at import time
    via the per-request `learning.LEARNING_LOG_PATH` lookup in routes/learning.py)."""
    log = icloud_base / "learning_log.jsonl"
    with log.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    import services.learning
    importlib.reload(services.learning)


@pytest.fixture(autouse=True)
def _reload_learning_module():
    """Ensure services.learning reflects whichever ICLOUD_BASE_PATH the test
    fixtures patched. Runs after icloud_base if present."""
    yield
    import services.learning
    importlib.reload(services.learning)


@pytest.mark.asyncio
async def test_learning_log_returns_recent_entries(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-15T10:00:00Z", "type": "embedding_update", "job_id": "j-1", "speaker_name": "Pascal"},
        {"ts": "2026-05-15T11:00:00Z", "type": "glossary_add", "job_id": "j-1", "term": "Manukai"},
        {"ts": "2026-05-15T12:00:00Z", "type": "insight_added", "job_id": "j-1", "speaker_name": "David", "category": "explicit", "count": 1},
    ])

    resp = await client.get("/learning/log")
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert "total" in body
    assert body["total"] == 3
    # Default order: most recent first
    assert body["events"][0]["type"] == "insight_added"
    assert body["events"][-1]["type"] == "embedding_update"


@pytest.mark.asyncio
async def test_learning_log_filter_by_type(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-15T10:00:00Z", "type": "embedding_update", "job_id": "j-1"},
        {"ts": "2026-05-15T11:00:00Z", "type": "glossary_add", "job_id": "j-1", "term": "X"},
        {"ts": "2026-05-15T12:00:00Z", "type": "embedding_update", "job_id": "j-2"},
    ])
    resp = await client.get("/learning/log?type=embedding_update")
    body = resp.json()
    assert body["total"] == 2
    assert all(e["type"] == "embedding_update" for e in body["events"])


@pytest.mark.asyncio
async def test_learning_log_filter_by_since(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-14T10:00:00Z", "type": "embedding_update", "job_id": "old"},
        {"ts": "2026-05-15T10:00:00Z", "type": "glossary_add", "job_id": "new", "term": "X"},
    ])
    resp = await client.get("/learning/log?since=2026-05-15T00:00:00Z")
    body = resp.json()
    assert body["total"] == 1
    assert body["events"][0]["job_id"] == "new"


@pytest.mark.asyncio
async def test_learning_log_pagination(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": f"2026-05-15T10:00:{i:02d}Z", "type": "glossary_add", "job_id": f"j-{i}", "term": f"T{i}"}
        for i in range(10)
    ])
    resp = await client.get("/learning/log?limit=3&offset=2")
    body = resp.json()
    assert len(body["events"]) == 3
    # offset=2 starts at the 3rd most-recent event
    assert body["events"][0]["job_id"] == "j-7"  # 0-indexed from end: j-9 (offset 0), j-8 (1), j-7 (2)


@pytest.mark.asyncio
async def test_learning_log_missing_file_returns_empty(client, icloud_base):
    # Don't seed any log file
    resp = await client.get("/learning/log")
    assert resp.status_code == 200
    body = resp.json()
    assert body["events"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_learning_log_rejects_oversize_limit(client, icloud_base):
    """limit > 500 must be clamped or rejected."""
    resp = await client.get("/learning/log?limit=10000")
    # Either 400 or auto-clamped to 500 — both acceptable; check it doesn't OOM
    assert resp.status_code in (200, 400, 422)
```

- [ ] **Step 2: Run; verify failure (404)**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_log_route.py -v 2>&1 | tail -10
```

- [ ] **Step 3: Implement `backend/routes/learning.py`**

```python
"""B7 endpoint: read the learning log for the Activity timeline."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

# Import the MODULE, not the constant — tests reload services.learning to
# repoint LEARNING_LOG_PATH at the icloud_base fixture's tmp path. Importing
# the constant directly would capture the production path at module load.
from services import learning

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])

MAX_LIMIT = 500


@router.get("/log")
async def get_learning_log(
    since: Optional[str] = Query(None, description="ISO timestamp lower bound (inclusive)"),
    type: Optional[str] = Query(None, description="Event type filter (embedding_update, glossary_add, insight_added, ...)"),
    limit: int = Query(100, ge=1, le=MAX_LIMIT, description="Max events to return (cap 500)"),
    offset: int = Query(0, ge=0, description="Skip the first N most-recent events"),
):
    """Return learning events, most recent first."""
    log_path = learning.LEARNING_LOG_PATH  # resolved per-request, not at import
    if not log_path.is_file():
        return {"events": [], "total": 0, "offset": offset, "limit": limit}

    matching: list = []
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if type and record.get("type") != type:
                    continue
                if since and record.get("ts", "") < since:
                    continue
                matching.append(record)
    except OSError:
        logger.warning("learning_log read failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read learning log")

    # Also tell the route's test fixture which path was used (debugging only).

    matching.reverse()  # most-recent first
    total = len(matching)
    page = matching[offset:offset + limit]
    return {"events": page, "total": total, "offset": offset, "limit": limit}
```

- [ ] **Step 4: Register router in `backend/main.py`**

After the existing `app.include_router(refinement_router, dependencies=_rate_dep)` line, add:

```python
from routes.learning import router as learning_router
app.include_router(learning_router, dependencies=_rate_dep)
```

Place the import alongside the other route imports near the top of `main.py`.

- [ ] **Step 5: Run endpoint tests**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_log_route.py -v 2>&1 | tail -15
```
Expected: 6 passed.

- [ ] **Step 6: Full suite regression check**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: 306 passed (300 + 6), 3 skipped.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/learning.py backend/main.py backend/tests/test_learning_log_route.py
git commit -m "B7: add GET /learning/log endpoint with type/since/limit filters"
```

---

## Task 8: Surface `learning_summary` in GET `/job/{id}` (verify Plan 1 wiring)

**Files:**
- Verify: `backend/routes/transcription.py` — the GET handler already emits `learning_summary` and `learning_status` (added in Plan 1 Task 6)
- Modify: `backend/tests/test_auto_refine_orchestration.py` — add a verification test

Plan 1 Task 6 added these fields to the GET response. Plan 2 just populates them via the orchestrator. Add a regression test that the populated values round-trip through the API.

- [ ] **Step 1: Add test to `backend/tests/test_auto_refine_orchestration.py`**

```python
@pytest.mark.asyncio
async def test_learning_summary_round_trips_through_api(client, sample_job):
    """After populating job.learning_summary, GET /job/{id} returns it."""
    import state
    job = state.jobs.get(sample_job)
    assert job is not None
    job.learning_summary = {"embeddings_updated": 1, "insights_added": 2, "terms_learned": 3}
    job.learning_status = "ok"
    state.jobs.update(job)

    resp = await client.get(f"/job/{sample_job}")
    body = resp.json()
    assert body["learning_status"] == "ok"
    assert body["learning_summary"] == {
        "embeddings_updated": 1, "insights_added": 2, "terms_learned": 3,
    }
```

- [ ] **Step 2: Run; verify pass**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_auto_refine_orchestration.py -v 2>&1 | tail -15
```
Expected: 16 passed (15 prior + 1 new).

- [ ] **Step 3: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/tests/test_auto_refine_orchestration.py
git commit -m "B7: regression test — learning_summary round-trips through GET /job"
```

---

## Task 9: Manual validation gate — re-run Pascal Weber audio

**Files:**
- None (manual gate)

The acceptance criteria for Plan 2:
1. `learning_log.jsonl` exists at `~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/learning_log.jsonl`.
2. After a full transcribe→refine→learn cycle, the log contains `glossary_add` events for any high-confidence corrections beyond what's already seeded in `_global.md`.
3. `GET /job/{job_id}` returns `learning_status: "ok"` and a non-zero `learning_summary`.
4. `GET /learning/log` returns the new events.
5. `_global.md` "Auto-learned (pending review)" section is no longer empty.

- [ ] **Step 1: Restart backend to pick up new code**

```bash
launchctl kickstart -k "gui/$(id -u)/com.whisper.backend"
until curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; do sleep 3; done
echo "backend ready"
```

- [ ] **Step 2: Verify learning router is registered**

```bash
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(k for k in d['paths'].keys() if 'learning' in k))"
```
Expected: `/learning/log`.

- [ ] **Step 3: Snapshot current `_global.md` so we can diff later**

```bash
cp "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md" /tmp/_global.before.md
```

- [ ] **Step 4: Submit a transcription job (same shape as Plan 1 Task 12)**

```bash
PASCAL=46b62a83-7f38-4c14-a2c0-e7ffa321510b
DAVID=3bff667f-424d-4b38-a78b-f45884af3489
curl -s -X POST "http://127.0.0.1:8000/transcribe/file?language=auto&enable_diarization=true&engine=whisper&model_size=large-v3-turbo&num_speakers=2&speaker_ids=${PASCAL}&speaker_ids=${DAVID}" \
  -F "file=@$HOME/Development/apps/whisper-transcription-app/Tests/15-29-21.m4a" \
  | tee /tmp/plan2-job.json
JOB_ID=$(python3 -c "import json; print(json.load(open('/tmp/plan2-job.json'))['job_id'])")
echo "JOB_ID=$JOB_ID"
```

- [ ] **Step 5: Poll until status=completed (~7-10 min)**

```bash
until [ "$(curl -s "http://127.0.0.1:8000/job/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')" = "completed" ]; do sleep 15; done
echo "transcription completed"
```

- [ ] **Step 6: Poll until refinement+learning done (~3 min)**

```bash
until [ "$(curl -s "http://127.0.0.1:8000/job/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("refinement_status") or "")')" = "done" ]; do sleep 10; done
echo "refinement+learning done"
curl -s "http://127.0.0.1:8000/job/$JOB_ID" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('learning_status:', d.get('learning_status'))
print('learning_summary:', d.get('learning_summary'))
"
```

- [ ] **Step 7: Verify `learning_log.jsonl` was populated**

```bash
LOG="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/learning_log.jsonl"
ls -la "$LOG"
echo "=== Last 10 entries ==="
tail -10 "$LOG" | python3 -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    r = json.loads(line)
    print(f\"  {r['ts']} {r['type']:18s} {r.get('speaker_name','-'):15s} {r.get('term','-')}\")
"
```

- [ ] **Step 8: Verify `/learning/log` endpoint returns those entries**

```bash
curl -s "http://127.0.0.1:8000/learning/log?limit=20" | python3 -m json.tool | head -30
```

- [ ] **Step 9: Verify `_global.md` got pending-review entries**

```bash
diff /tmp/_global.before.md "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md"
```
Expected: net additions under `## Auto-learned (pending review)`.

- [ ] **Step 10: Final regression run + push**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
cd ~/Development/apps/whisper-transcription-app && git push origin dev
```

---

## Done criteria

Plan 2 is complete when:
- All 8 task commits land on `dev`.
- Full backend pytest suite passes (~307 tests).
- A real transcription run produces (a) a non-empty `learning_log.jsonl`, (b) `learning_status="ok"` on the job, (c) new pending-review terms in `_global.md`, (d) the activity entries visible through `GET /learning/log`.
- Branch pushed to `origin/dev`.

Plan 3 (UX surface for B6) can start from this baseline.

## Out of scope (explicit)

- Voice embeddings for direct-uploaded audio when the user did NOT use JPR — the tmp file is preserved by the deferred-cleanup logic only as long as the auto-refine path runs. If the user manually navigates to refinement post-restart, audio is gone and the embedding worker skips with `audio_unavailable`.
- Streaming the learning log (e.g. WebSocket push for live UI). Polling `GET /learning/log` is sufficient for Plan 3.
- Compaction / rotation of the JSONL file. The file is append-only; at the expected event rate (~10 events/job × dozens of jobs/month) it stays well under 1MB/year.
- Rich event types (e.g. confidence histograms, alignment metrics). Plan 2 ships the 5 event types the spec lists: `embedding_update`, `embedding_skipped`, `embedding_failed`, `glossary_add`, `insight_added`, `insight_failed`.
