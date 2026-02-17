-- Migration 002: Create schema_version tracking table

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
