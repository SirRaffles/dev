-- Migration 001: Speaker registry, call-speaker associations, call metadata
-- Supports the call intelligence features: speaker management, context folders, deliverables

-- Persistent speaker registry
CREATE TABLE IF NOT EXISTS speakers (
    speaker_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    folder_path TEXT NOT NULL,
    embedding_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    call_count INTEGER DEFAULT 0,
    total_speaking_time_seconds REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_speakers_name ON speakers(name);

-- Call-speaker associations (many-to-many)
CREATE TABLE IF NOT EXISTS call_speakers (
    call_id TEXT NOT NULL,
    speaker_id TEXT NOT NULL,
    speaker_label TEXT,
    confidence REAL DEFAULT 0,
    confirmed INTEGER DEFAULT 0,
    speaking_time_seconds REAL DEFAULT 0,
    PRIMARY KEY (call_id, speaker_id)
);

CREATE INDEX IF NOT EXISTS idx_call_speakers_call ON call_speakers(call_id);
CREATE INDEX IF NOT EXISTS idx_call_speakers_speaker ON call_speakers(speaker_id);

-- Call metadata (extends jobs with context/deliverable tracking)
CREATE TABLE IF NOT EXISTS call_metadata (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    context_path TEXT,
    call_folder_path TEXT,
    speakers_identified INTEGER DEFAULT 0,
    context_assigned INTEGER DEFAULT 0,
    deliverables_generated INTEGER DEFAULT 0,
    deliverables_generated_at TIMESTAMP,
    source_type TEXT DEFAULT 'upload',
    source_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_metadata_context ON call_metadata(context_path);
CREATE INDEX IF NOT EXISTS idx_call_metadata_source ON call_metadata(source_type);
