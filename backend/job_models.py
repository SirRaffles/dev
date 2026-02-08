"""
Job data models and storage.
"""

import os
import json
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TranscriptionJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"  # pending, processing, completed, failed
        self.progress = 0
        self.progress_message = ""
        self.result = None
        self.error = None
        self.language = None
        self.language_probability = None
        self.segments = []
        self.speakers = []  # Speaker diarization results


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

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
            ''')
            conn.commit()
        logger.info(f"Job store initialized at {self.db_path}")

    def _load_active_jobs(self):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE status IN ('pending', 'processing')"
            )
            for row in cursor.fetchall():
                job = self._row_to_job(row)
                self._cache[job.job_id] = job
        logger.info(f"Loaded {len(self._cache)} active jobs from database")

    def _row_to_job(self, row) -> TranscriptionJob:
        job = TranscriptionJob(row[0])
        job.status = row[1]
        job.progress = row[2] or 0
        job.progress_message = row[3] or ""
        job.result = json.loads(row[4]) if row[4] else None
        job.error = row[5]
        job.language = row[6]
        job.language_probability = row[7]
        job.segments = json.loads(row[8]) if row[8] else []
        job.speakers = json.loads(row[9]) if row[9] else []
        return job

    def _job_to_row(self, job: TranscriptionJob, file_path: str = None) -> tuple:
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
        )

    def create(self, job: TranscriptionJob, file_path: str = None):
        with self._lock:
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO jobs (job_id, status, progress, progress_message,
                                     result, error, language, language_probability,
                                     segments, speakers, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', self._job_to_row(job, file_path))
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
                    job = self._row_to_job(row)
                    self._cache[job_id] = job
                    return job
            return None

    def update(self, job: TranscriptionJob):
        with self._lock:
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    UPDATE jobs SET status=?, progress=?, progress_message=?,
                                   result=?, error=?, language=?, language_probability=?,
                                   segments=?, speakers=?, updated_at=CURRENT_TIMESTAMP
                    WHERE job_id=?
                ''', (
                    job.status, job.progress, job.progress_message,
                    json.dumps(job.result) if job.result else None,
                    job.error, job.language, job.language_probability,
                    json.dumps(job.segments) if job.segments else None,
                    json.dumps(job.speakers) if job.speakers else None,
                    job.job_id
                ))
                conn.commit()

    def delete(self, job_id: str):
        with self._lock:
            self._cache.pop(job_id, None)
            with self._get_connection() as conn:
                conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
                conn.commit()

    def get_all(self) -> dict:
        return dict(self._cache)

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
    model_size: str = "large-v3-turbo"
    translate_to_english: bool = False
    engine: str = "whisper"
    context_terms: Optional[List[str]] = None


class SpeakerRenameRequest(BaseModel):
    speaker_mapping: dict  # {"old_name": "new_name"}


class SegmentUpdate(BaseModel):
    segments: List[dict]  # [{start, end, text, speaker}]
