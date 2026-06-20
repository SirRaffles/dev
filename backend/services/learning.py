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
import app_state

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


MIN_LEARNING_DURATION_SEC = 60.0
EMA_ALPHA = 0.3


def update_speaker_embeddings(
    job_id: str,
    audio_path: Optional[str],
    speaker_turns: list,
    assignments: dict,
) -> int:
    """EMA-merge fresh voice embeddings for named speakers with >=60s of speech.

    Args:
        job_id: For the learning_log event.
        audio_path: Path to the original audio file. None or missing -> skip.
        speaker_turns: pyannote diarization [{start, end, speaker}, ...].
        assignments: {pyannote_label: speaker_name} for speakers we recognized
            (built by the orchestrator from refined segments).

    Returns: number of speakers whose embedding was updated.
    Never raises - caller wraps in try/except for the orchestrator's status rollup.
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


def _extract_speaker_insights_sync(job_id: str) -> dict:
    """For each named (non-anonymous) speaker in the job's segments, refresh
    both their EXPLICIT-insights and IMPLICIT-insights markdown from this
    transcript. The user-maintained `profile.md` (bio) is never touched
    by the LLM.

    Result shape: {
      "updated": ["Arnaud:explicit", "Arnaud:implicit", ...],
      "skipped": [{speaker, reason}, ...],
      "errors":  ["Arnaud:explicit: <err>", ...]
    }"""
    result = {"updated": [], "skipped": [], "errors": []}

    if not app_state.deliverable_available() or app_state.deliverable_service() is None:
        result["errors"].append("claude CLI not available — insights skipped")
        return result

    job = app_state.jobs().get(job_id)
    if not job or not job.segments:
        result["errors"].append("job has no segments")
        return result

    from services.deliverable_service import _build_transcript_text, SPEAKERS_DIR
    from services.labels import is_anonymous_label

    named = {
        (seg.get("speaker") or "").strip()
        for seg in job.segments
        if seg.get("speaker") and not is_anonymous_label(seg.get("speaker"))
    }
    if not named:
        result["errors"].append("no named speakers to extract insights for")
        return result

    transcript_text = _build_transcript_text(job.segments)

    sections = (
        ("explicit", "explicit_insights.md", "update_explicit_insights"),
        ("implicit", "implicit_insights.md", "update_implicit_insights"),
    )

    for name in sorted(named):
        speaker_lines = [
            line for line in transcript_text.split("\n")
            if f"] {name}:" in line
        ]
        if not speaker_lines:
            result["skipped"].append({"speaker": name, "reason": "no lines"})
            continue
        speaker_transcript = "\n".join(speaker_lines[:100])

        speaker_folder = SPEAKERS_DIR / name
        speaker_folder.mkdir(parents=True, exist_ok=True)

        for tag, filename, method_name in sections:
            try:
                path = speaker_folder / filename
                existing = path.read_text(encoding="utf-8") if path.exists() else ""
                logger.info("Updating %s for %s from job %s", tag, name, job_id)
                method = getattr(app_state.deliverable_service(), method_name)
                updated = method(name, speaker_transcript, existing)
                path.write_text(updated, encoding="utf-8")
                result["updated"].append(f"{name}:{tag}")
            except Exception as e:
                logger.error("Insight extraction failed for %s:%s: %s", name, tag, e, exc_info=True)
                result["errors"].append(f"{name}:{tag}: {e}")

    return result


def extract_insights_auto(job_id: str) -> int:
    """Refresh explicit + implicit insights for every named speaker in the job's
    refined segments. Records one 'insight_added' event per (speaker, category).

    Returns the count of (speaker, category) pairs successfully updated.
    Never raises.
    """
    try:
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

    # Per-speaker errors from the helper (Claude API failure, parse failure, etc.).
    # Surface each as an insight_failed event so B7 doesn't silently drop them.
    errors = result.get("errors", []) if isinstance(result, dict) else []
    for err in errors:
        # _extract_speaker_insights_sync emits errors as either a list of strings
        # ("Name:category: <traceback snippet>") or dicts. Handle both shapes
        # defensively — we don't own the upstream format.
        if isinstance(err, str):
            head, sep, reason = err.partition(":")
            speaker_name = head.strip().split(":")[0] if sep else ""
            err_text = (sep + reason).strip(": ").strip() if sep else err
        elif isinstance(err, dict):
            speaker_name = str(err.get("speaker", "")).strip()
            err_text = str(err.get("error", err.get("reason", "")))
        else:
            speaker_name = ""
            err_text = str(err)
        record_event(
            "insight_failed",
            job_id=job_id,
            speaker_name=speaker_name,
            reason=err_text[:200],
        )
    return count


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
