-- Extend library_items schema for Story 4.2 persistence requirements

ALTER TABLE library_items ADD COLUMN job_id TEXT;
ALTER TABLE library_items ADD COLUMN source_path TEXT;
ALTER TABLE library_items ADD COLUMN format TEXT;
ALTER TABLE library_items ADD COLUMN byte_size INTEGER;

CREATE INDEX IF NOT EXISTS idx_library_items_job_id
    ON library_items(job_id);

