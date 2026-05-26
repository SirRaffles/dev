"""
Job data models and storage.
"""

import os
import json
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SPEAKER_REVIEW_NOT_NEEDED = "not_needed"
SPEAKER_REVIEW_NEEDS_REVIEW = "needs_review"
SPEAKER_REVIEW_REVIEWED = "reviewed"


class TranscriptionJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.created_at = None
        self.status = "pending"  # pending, processing, completed, failed
        self.progress = 0
        self.progress_message = ""
        self.result = None
        self.error = None
        self.language = None
        self.language_probability = None
        self.segments = []
        self.speakers = []  # Speaker diarization results
        self.is_generated = False  # True when transcript came from auto-generated YT captions
        self._from_captions = False  # True when the job used the YouTube captions fast-path
        # B2 lifecycle fields.
        self.refinement_status = None       # None | "pending" | "processing" | "done" | "failed"
        self.auto_speaker_matches = None    # Dict[str, Dict] from B5
        self.learning_summary = None        # Dict[str, int] populated by Plan 2
        self.learning_status = None         # "ok" | "partial" | "failed" — populated by Plan 2
        # Plan 4A: phase pill for the UI's phased progress bar. Values:
        # None | "diarizing" | "transcribing" |
        # "aligning" | "refining" | "learning". None = no active phase.
        self.phase = None
        # Speaker review is a UX signal, not a refinement gate.
        self.speaker_review_status = SPEAKER_REVIEW_NEEDS_REVIEW
        # Compatibility alias for older frontend/backend code.
        self.speakers_resolved = False


def _review_status_from_resolved(resolved: bool) -> str:
    return SPEAKER_REVIEW_NOT_NEEDED if resolved else SPEAKER_REVIEW_NEEDS_REVIEW


def _resolved_from_review_status(status: Optional[str]) -> bool:
    return status != SPEAKER_REVIEW_NEEDS_REVIEW


def _job_review_status(job) -> str:
    status = getattr(job, "speaker_review_status", None)
    if getattr(job, "speakers_resolved", False) and status == SPEAKER_REVIEW_NEEDS_REVIEW:
        return SPEAKER_REVIEW_NOT_NEEDED
    if status in (
        SPEAKER_REVIEW_NOT_NEEDED,
        SPEAKER_REVIEW_NEEDS_REVIEW,
        SPEAKER_REVIEW_REVIEWED,
    ):
        return status
    return _review_status_from_resolved(getattr(job, "speakers_resolved", False))


class BatchJob:
    def __init__(self, batch_id: str, job_ids: List[str]):
        self.batch_id = batch_id
        self.job_ids = job_ids
        self.created_at = datetime.now()
        self.total = len(job_ids)


class JobStore:
    """
    SQLite-backed job storage with in-memory cache.
    Provides persistence across backend restarts.
    """

    # Audit #14: run prune_completed every hour via a daemon thread instead of
    # on every create().
    _PRUNE_INTERVAL_SECONDS = 3600

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._cache = {}
        self._lock = threading.Lock()
        self._init_db()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass
        self._load_active_jobs()
        self._cleanup_stale_pending()
        # Start background prune timer (daemon thread exits with the process).
        self._prune_stop = threading.Event()
        self._prune_thread = threading.Thread(
            target=self._prune_loop, daemon=True, name="job-prune"
        )
        self._prune_thread.start()

    def _get_connection(self):
        # TODO(audit #14): switch to thread-local cached connections. Current
        # implementation opens a fresh handle per call, which is safe but slow.
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
            # Audit #14: WAL + relaxed sync + in-memory temp + mmap for perf.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    progress_message TEXT,
                    result TEXT,
                    error TEXT,
                    language TEXT,
                    language_probability REAL,
                    segments TEXT,
                    speakers TEXT,
                    file_path TEXT,
                    settings TEXT,
                    youtube_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
            ''')
            # Migrate existing DB: add columns if missing
            existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
            if 'settings' not in existing:
                conn.execute("ALTER TABLE jobs ADD COLUMN settings TEXT")
            if 'youtube_url' not in existing:
                conn.execute("ALTER TABLE jobs ADD COLUMN youtube_url TEXT")
            for column, ddl_type in (
                ("phase", "TEXT"),
                ("refinement_status", "TEXT"),
                ("speaker_review_status", "TEXT"),
                ("auto_speaker_matches", "TEXT"),
                ("learning_status", "TEXT"),
                ("learning_summary", "TEXT"),
            ):
                if column not in existing:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {ddl_type}")
            conn.commit()
        logger.info(f"Job store initialized at {self.db_path}")

    def _cleanup_stale_pending(self):
        """Mark jobs stuck in pending/processing for >24h as failed on startup."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status='failed', error='stale: auto-cleaned on startup', "
                "updated_at=CURRENT_TIMESTAMP "
                "WHERE status IN ('pending', 'processing') "
                "AND updated_at < datetime('now', '-24 hours')"
            )
            if cursor.rowcount:
                conn.commit()
                logger.info("Cleaned %d stale pending/processing jobs", cursor.rowcount)

    def _load_active_jobs(self):
        with self._get_connection() as conn:
            # Any "processing" OR "pending" job from a previous backend
            # instance is orphaned — processing jobs lost their executor
            # thread; pending jobs lost their executor.submit() call from
            # the route handler. Neither will resume on its own, so mark
            # them all as failed and let the user retry.
            orphan_cursor = conn.execute(
                "UPDATE jobs SET status='failed', "
                "error='Backend restarted mid-job — please retry', "
                "updated_at=CURRENT_TIMESTAMP "
                "WHERE status IN ('processing', 'pending')"
            )
            if orphan_cursor.rowcount:
                conn.commit()
                logger.info(
                    "Marked %d orphan 'processing'/'pending' jobs as failed on startup",
                    orphan_cursor.rowcount,
                )
            # No active jobs survive a restart — the executor work is lost.
            # Leaving _cache empty matches that reality; the UI shows real
            # failure states + retry buttons instead of zombie polling.
        logger.info(f"Loaded {len(self._cache)} active jobs from database")

    def _prune_loop(self):
        while not self._prune_stop.wait(self._PRUNE_INTERVAL_SECONDS):
            try:
                self.prune_completed()
            except Exception as exc:
                logger.warning("Periodic prune_completed failed: %s", exc)

    @staticmethod
    def _loads_json(value, default=None):
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def _row_to_job(self, row, description=None) -> TranscriptionJob:
        columns = [col[0] for col in description] if description else []

        def by_name(name: str, fallback_index: int = None, default=None):
            if name in columns:
                return row[columns.index(name)]
            if fallback_index is not None and fallback_index < len(row):
                return row[fallback_index]
            return default

        job = TranscriptionJob(by_name("job_id", 0))
        job.status = by_name("status", 1)
        job.progress = by_name("progress", 2) or 0
        job.progress_message = by_name("progress_message", 3) or ""
        job.result = self._loads_json(by_name("result", 4), None)
        job.error = by_name("error", 5)
        job.language = by_name("language", 6)
        job.language_probability = by_name("language_probability", 7)
        job.segments = self._loads_json(by_name("segments", 8), []) or []
        job.speakers = self._loads_json(by_name("speakers", 9), []) or []
        job.phase = by_name("phase")
        job.refinement_status = by_name("refinement_status")
        job.auto_speaker_matches = self._loads_json(by_name("auto_speaker_matches"), None)
        job.learning_status = by_name("learning_status")
        job.learning_summary = self._loads_json(by_name("learning_summary"), None)
        job.created_at = by_name("created_at")

        review_status = by_name("speaker_review_status")
        if review_status in (
            SPEAKER_REVIEW_NOT_NEEDED,
            SPEAKER_REVIEW_NEEDS_REVIEW,
            SPEAKER_REVIEW_REVIEWED,
        ):
            job.speaker_review_status = review_status
        elif job.status == "completed":
            # Completed rows created before speaker review existed should not
            # render as needing action after reload.
            job.speaker_review_status = SPEAKER_REVIEW_NOT_NEEDED
        else:
            job.speaker_review_status = SPEAKER_REVIEW_NEEDS_REVIEW
        job.speakers_resolved = _resolved_from_review_status(job.speaker_review_status)

        settings_raw = self._loads_json(by_name("settings"), None)
        if settings_raw:
            try:
                job.settings = TranscriptionSettings(**settings_raw)
            except Exception:
                job.settings = settings_raw
        return job

    def _job_to_row(self, job: TranscriptionJob, file_path: str = None, settings: dict = None, youtube_url: str = None) -> tuple:
        return (
            job.job_id,
            job.status,
            job.progress,
            job.progress_message,
            json.dumps(job.result) if job.result else None,
            job.error,
            job.language,
            job.language_probability,
            json.dumps(job.segments) if job.segments else None,
            json.dumps(job.speakers) if job.speakers else None,
            file_path,
            json.dumps(settings) if settings else None,
            youtube_url,
            job.phase,
            job.refinement_status,
            _job_review_status(job),
            json.dumps(job.auto_speaker_matches) if job.auto_speaker_matches else None,
            job.learning_status,
            json.dumps(job.learning_summary) if job.learning_summary else None,
        )

    def prune_completed(self, max_age_hours: int = 720):
        """Remove completed/failed jobs older than max_age_hours from DB and cache."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM jobs WHERE status IN ('completed', 'failed') "
                    "AND updated_at < datetime('now', ? || ' hours')",
                    (f"-{max_age_hours}",)
                )
                pruned = cursor.rowcount
                conn.commit()
            if pruned:
                # Remove stale entries from cache too
                stale = [
                    jid for jid, j in self._cache.items()
                    if j.status in ("completed", "failed")
                ]
                # Keep only recent ones; cache doesn't track timestamps,
                # so evict all completed/failed beyond a size threshold
                if len(self._cache) > 500:
                    for jid in stale[:len(stale) - 100]:
                        self._cache.pop(jid, None)
                logger.info("Pruned %d completed/failed jobs older than %dh", pruned, max_age_hours)

    def create(self, job: TranscriptionJob, file_path: str = None, settings: dict = None, youtube_url: str = None):
        # Audit #14: prune is now a scheduled job; do not run it synchronously here.
        with self._lock:
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO jobs (job_id, status, progress, progress_message,
                                     result, error, language, language_probability,
                                     segments, speakers, file_path, settings, youtube_url,
                                     phase, refinement_status, speaker_review_status,
                                     auto_speaker_matches, learning_status, learning_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', self._job_to_row(job, file_path, settings, youtube_url))
                conn.commit()

    def get(self, job_id: str) -> Optional[TranscriptionJob]:
        with self._lock:
            if job_id in self._cache:
                return self._cache[job_id]
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                if row:
                    job = self._row_to_job(row, cursor.description)
                    self._cache[job_id] = job
                    return job
            return None

    def get_job_meta(self, job_id: str) -> Optional[dict]:
        """Return stored settings and youtube_url for a job (for retry)."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT file_path, settings, youtube_url FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "file_path": row[0],
                    "settings": json.loads(row[1]) if row[1] else None,
                    "youtube_url": row[2],
                }

    def update(self, job: TranscriptionJob):
        with self._lock:
            job.speaker_review_status = _job_review_status(job)
            job.speakers_resolved = _resolved_from_review_status(job.speaker_review_status)
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    UPDATE jobs SET status=?, progress=?, progress_message=?,
                                   result=?, error=?, language=?, language_probability=?,
                                   segments=?, speakers=?,
                                   phase=?, refinement_status=?, speaker_review_status=?,
                                   auto_speaker_matches=?, learning_status=?, learning_summary=?,
                                   updated_at=CURRENT_TIMESTAMP
                    WHERE job_id=?
                ''', (
                    job.status, job.progress, job.progress_message,
                    json.dumps(job.result) if job.result else None,
                    job.error, job.language, job.language_probability,
                    json.dumps(job.segments) if job.segments else None,
                    json.dumps(job.speakers) if job.speakers else None,
                    job.phase,
                    job.refinement_status,
                    _job_review_status(job),
                    json.dumps(job.auto_speaker_matches) if job.auto_speaker_matches else None,
                    job.learning_status,
                    json.dumps(job.learning_summary) if job.learning_summary else None,
                    job.job_id
                ))
                conn.commit()
            # Evict old completed/failed jobs from cache to bound memory
            if len(self._cache) > 1000:
                to_evict = [
                    jid for jid, j in self._cache.items()
                    if j.status in ("completed", "failed")
                ]
                for jid in to_evict[:len(self._cache) - 500]:
                    del self._cache[jid]

    def update_settings(self, job_id: str, settings: dict) -> None:
        """Replace the stored settings JSON for a job."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE jobs SET settings=?, updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
                    (json.dumps(settings) if settings else None, job_id),
                )
                conn.commit()

    def delete(self, job_id: str):
        with self._lock:
            self._cache.pop(job_id, None)
            with self._get_connection() as conn:
                conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
                conn.commit()

    def get_all(self) -> dict:
        return dict(self._cache)

    def list_recent(self, limit: int = 50, offset: int = 0, status: str = None) -> List[dict]:
        """List recent jobs from DB (not just cache). Returns lightweight summaries."""
        with self._lock:
            with self._get_connection() as conn:
                if status:
                    cursor = conn.execute(
                        "SELECT job_id, status, progress, progress_message, language, "
                        "created_at, updated_at, file_path "
                        "FROM jobs WHERE status = ? "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (status, limit, offset)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT job_id, status, progress, progress_message, language, "
                        "created_at, updated_at, file_path "
                        "FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    )
                rows = cursor.fetchall()
                return [
                    {
                        "job_id": r[0],
                        "status": r[1],
                        "progress": r[2] or 0,
                        "progress_message": r[3] or "",
                        "language": r[4],
                        "created_at": r[5],
                        "updated_at": r[6],
                        "file_path": os.path.basename(r[7]) if r[7] else None,
                    }
                    for r in rows
                ]

    def count(self, status: str = None) -> int:
        """Count jobs, optionally filtered by status."""
        with self._lock:
            with self._get_connection() as conn:
                if status:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM jobs")
                return cursor.fetchone()[0]

    def get_active_count(self) -> int:
        return len([j for j in self._cache.values() if j.status == "processing"])

    def __contains__(self, job_id: str) -> bool:
        return self.get(job_id) is not None

    def __len__(self) -> int:
        return len(self._cache)

    def __setitem__(self, job_id: str, job: TranscriptionJob):
        if job_id in self._cache:
            self.update(job)
        else:
            self.create(job)

    def __getitem__(self, job_id: str) -> TranscriptionJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def __delitem__(self, job_id: str):
        self.delete(job_id)

    def values(self):
        return self._cache.values()

    def keys(self):
        return self._cache.keys()

    def items(self):
        return self._cache.items()


# Pydantic request/response models

class YouTubeRequest(BaseModel):
    url: str
    language: str = "auto"
    enable_diarization: bool = True
    enable_noise_reduction: bool = False
    translate_to_english: bool = False


class TranscriptionSettings(BaseModel):
    beam_size: int = 5
    patience: float = 1.0
    best_of: int = 5
    vad_filter: bool = False
    word_timestamps: bool = False
    language: str = "auto"
    enable_diarization: bool = True
    num_speakers: Optional[int] = None
    enable_noise_reduction: bool = False
    translate_to_english: bool = False
    engine: Literal["auto-best", "auto-quick"] = "auto-best"
    context_terms: Optional[List[str]] = None
    context_path: Optional[str] = None  # Relative path under CONTEXTS_DIR to a .md context document
    speaker_ids: Optional[List[str]] = None  # Expected speakers — their personality.md is merged into the prompt
    # Original file name as the user sees it (e.g. "IMPACT & ACN catch-up.m4a").
    # Used by /jpr/recordings to correlate an in-flight job with its JPR file
    # so the recording row can show "Processing" while transcription runs.
    original_filename: Optional[str] = None
    two_pass: bool = False
    refinement_mode: Optional[Literal["auto", "always", "off"]] = None
    # B2: tri-state — None = Auto, True = Always, False = Off.
    # Auto refines when context_path, speaker_ids, or B5 auto-matched speakers exist.
    auto_refine: Optional[bool] = None


class RefinementStore:
    """
    SQLite-backed storage for transcript refinement results.
    Uses the same database as JobStore.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS refinements (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    analysis TEXT,
                    refined_segments TEXT,
                    speaker_mapping TEXT,
                    corrections_applied INTEGER DEFAULT 0,
                    speakers_identified INTEGER DEFAULT 0,
                    web_searches_performed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error TEXT
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_refinements_status ON refinements(status)
            ''')
            conn.commit()
        logger.info("Refinement store initialized")

    def create(self, job_id: str):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO refinements (job_id, status) VALUES (?, 'pending')",
                    (job_id,)
                )
                conn.commit()

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM refinements WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_dict(row, cursor.description)

    def update_status(self, job_id: str, status: str, error: str = None):
        with self._lock:
            with self._get_connection() as conn:
                if error:
                    conn.execute(
                        "UPDATE refinements SET status=?, error=? WHERE job_id=?",
                        (status, error, job_id)
                    )
                else:
                    conn.execute(
                        "UPDATE refinements SET status=? WHERE job_id=?",
                        (status, job_id)
                    )
                conn.commit()

    def save_result(self, job_id: str, result: dict):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute('''
                    UPDATE refinements SET
                        status='completed',
                        analysis=?,
                        refined_segments=?,
                        speaker_mapping=?,
                        corrections_applied=?,
                        speakers_identified=?,
                        web_searches_performed=?,
                        completed_at=CURRENT_TIMESTAMP
                    WHERE job_id=?
                ''', (
                    json.dumps(result.get("analysis")),
                    json.dumps(result.get("refined_segments")),
                    json.dumps(result.get("speaker_mapping")),
                    result.get("corrections_applied", 0),
                    result.get("speakers_identified", 0),
                    result.get("web_searches_performed", 0),
                    job_id,
                ))
                conn.commit()

    def _row_to_dict(self, row, description) -> dict:
        columns = [col[0] for col in description]
        d = dict(zip(columns, row))
        # Parse JSON fields
        for field in ("analysis", "refined_segments", "speaker_mapping"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d


class SpeakerRenameRequest(BaseModel):
    speaker_mapping: dict  # {"old_name": "new_name"}


class SegmentUpdate(BaseModel):
    segments: List[dict]  # [{start, end, text, speaker}]


# --- Call Intelligence Models ---


class SpeakerStore:
    """SQLite-backed storage for the persistent speaker registry."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._lock = threading.Lock()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def create(self, speaker_id: str, name: str, folder_path: str, embedding_path: str = None) -> dict:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO speakers (speaker_id, name, folder_path, embedding_path) "
                    "VALUES (?, ?, ?, ?)",
                    (speaker_id, name, folder_path, embedding_path),
                )
                conn.commit()
        return {"speaker_id": speaker_id, "name": name, "folder_path": folder_path}

    def get(self, speaker_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM speakers WHERE speaker_id = ?", (speaker_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_dict(row, cursor.description)

    def get_by_name(self, name: str) -> Optional[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM speakers WHERE name = ?", (name,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_dict(row, cursor.description)

    def list_all(self) -> List[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM speakers ORDER BY name"
                )
                return [self._row_to_dict(r, cursor.description) for r in cursor.fetchall()]

    def update(self, speaker_id: str, **kwargs) -> bool:
        allowed = {"name", "folder_path", "embedding_path", "call_count", "total_speaking_time_seconds"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [speaker_id]
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    f"UPDATE speakers SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE speaker_id=?",
                    values,
                )
                conn.commit()
        return True

    def delete(self, speaker_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM speakers WHERE speaker_id=?", (speaker_id,))
                conn.commit()
                return cursor.rowcount > 0

    def increment_call_count(self, speaker_id: str, speaking_time: float = 0):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE speakers SET call_count = call_count + 1, "
                    "total_speaking_time_seconds = total_speaking_time_seconds + ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE speaker_id = ?",
                    (speaking_time, speaker_id),
                )
                conn.commit()

    def _row_to_dict(self, row, description) -> dict:
        columns = [col[0] for col in description]
        return dict(zip(columns, row))


class CallSpeakerStore:
    """SQLite-backed storage for call-speaker associations."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._lock = threading.Lock()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def add(self, call_id: str, speaker_id: str, speaker_label: str = None,
            confidence: float = 0, speaking_time: float = 0) -> dict:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO call_speakers "
                    "(call_id, speaker_id, speaker_label, confidence, speaking_time_seconds) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (call_id, speaker_id, speaker_label, confidence, speaking_time),
                )
                conn.commit()
        return {"call_id": call_id, "speaker_id": speaker_id}

    def confirm(self, call_id: str, speaker_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE call_speakers SET confirmed=1 WHERE call_id=? AND speaker_id=?",
                    (call_id, speaker_id),
                )
                conn.commit()
                return cursor.rowcount > 0

    def get_for_call(self, call_id: str) -> List[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT cs.*, s.name as speaker_name FROM call_speakers cs "
                    "LEFT JOIN speakers s ON cs.speaker_id = s.speaker_id "
                    "WHERE cs.call_id = ?",
                    (call_id,),
                )
                return [self._row_to_dict(r, cursor.description) for r in cursor.fetchall()]

    def get_for_speaker(self, speaker_id: str) -> List[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT cs.*, cm.title as call_title FROM call_speakers cs "
                    "LEFT JOIN call_metadata cm ON cs.call_id = cm.job_id "
                    "WHERE cs.speaker_id = ? ORDER BY cs.call_id DESC",
                    (speaker_id,),
                )
                return [self._row_to_dict(r, cursor.description) for r in cursor.fetchall()]

    def all_confirmed(self, call_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM call_speakers WHERE call_id=? AND confirmed=0",
                    (call_id,),
                )
                return cursor.fetchone()[0] == 0

    def delete_for_call(self, call_id: str):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM call_speakers WHERE call_id=?", (call_id,))
                conn.commit()

    def _row_to_dict(self, row, description) -> dict:
        columns = [col[0] for col in description]
        return dict(zip(columns, row))


class CallMetadataStore:
    """SQLite-backed storage for call metadata (context, deliverables, etc.)."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._lock = threading.Lock()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def create(self, job_id: str, source_type: str = "upload", source_path: str = None,
               title: str = None) -> dict:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO call_metadata "
                    "(job_id, source_type, source_path, title) VALUES (?, ?, ?, ?)",
                    (job_id, source_type, source_path, title),
                )
                conn.commit()
        return {"job_id": job_id, "source_type": source_type}

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM call_metadata WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_dict(row, cursor.description)

    def update(self, job_id: str, **kwargs) -> bool:
        allowed = {
            "title", "context_path", "call_folder_path",
            "speakers_identified", "context_assigned",
            "deliverables_generated", "deliverables_generated_at",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [job_id]
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    f"UPDATE call_metadata SET {set_clause}, updated_at=CURRENT_TIMESTAMP "
                    f"WHERE job_id=?",
                    values,
                )
                conn.commit()
        return True

    def list_recent(self, limit: int = 50, offset: int = 0, status_filter: str = None) -> List[dict]:
        with self._lock:
            with self._get_connection() as conn:
                if status_filter == "pending_speakers":
                    cursor = conn.execute(
                        "SELECT * FROM call_metadata WHERE speakers_identified=0 "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                elif status_filter == "pending_context":
                    cursor = conn.execute(
                        "SELECT * FROM call_metadata WHERE speakers_identified=1 AND context_assigned=0 "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                elif status_filter == "ready":
                    cursor = conn.execute(
                        "SELECT * FROM call_metadata WHERE speakers_identified=1 "
                        "AND context_assigned=1 AND deliverables_generated=0 "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                elif status_filter == "delivered":
                    cursor = conn.execute(
                        "SELECT * FROM call_metadata WHERE deliverables_generated=1 "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM call_metadata ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                return [self._row_to_dict(r, cursor.description) for r in cursor.fetchall()]

    def count(self, status_filter: str = None) -> int:
        with self._lock:
            with self._get_connection() as conn:
                if status_filter == "pending_speakers":
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM call_metadata WHERE speakers_identified=0"
                    )
                elif status_filter == "delivered":
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM call_metadata WHERE deliverables_generated=1"
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM call_metadata")
                return cursor.fetchone()[0]

    def delete(self, job_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM call_metadata WHERE job_id=?", (job_id,))
                conn.commit()
                return cursor.rowcount > 0

    def _row_to_dict(self, row, description) -> dict:
        columns = [col[0] for col in description]
        return dict(zip(columns, row))
