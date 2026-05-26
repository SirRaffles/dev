-- Migration 004: Persist job lifecycle fields that were previously in memory.

ALTER TABLE jobs ADD COLUMN phase TEXT;
ALTER TABLE jobs ADD COLUMN refinement_status TEXT;
ALTER TABLE jobs ADD COLUMN speaker_review_status TEXT;
ALTER TABLE jobs ADD COLUMN auto_speaker_matches TEXT;
ALTER TABLE jobs ADD COLUMN learning_status TEXT;
ALTER TABLE jobs ADD COLUMN learning_summary TEXT;
