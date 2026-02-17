-- Migration 001: Initial schema (jobs + refinements tables)

PRAGMA journal_mode=WAL;

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
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

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
);

CREATE INDEX IF NOT EXISTS idx_refinements_status ON refinements(status);
