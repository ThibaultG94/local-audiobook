-- Extend library_items schema for Story 4.2 persistence requirements
--
-- Note: The following columns already exist from migration 0001:
--   - id, document_id, audio_path, title, source_format, engine, voice, language, duration_seconds, created_at
-- This migration adds:
--   - job_id: Link to conversion job that produced this library item
--   - source_path: Original source document path for reference
--   - format: Output audio format (mp3, wav)
--   - byte_size: Size of audio file in bytes

ALTER TABLE library_items ADD COLUMN job_id TEXT;
ALTER TABLE library_items ADD COLUMN source_path TEXT;
ALTER TABLE library_items ADD COLUMN format TEXT;
ALTER TABLE library_items ADD COLUMN byte_size INTEGER;

CREATE INDEX IF NOT EXISTS idx_library_items_job_id
    ON library_items(job_id);

