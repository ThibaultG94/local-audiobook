CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    state TEXT NOT NULL,
    engine TEXT,
    voice TEXT,
    language TEXT,
    speech_rate REAL,
    output_format TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_conversion_jobs_document_id
    ON conversion_jobs(document_id);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    content_hash TEXT,
    audio_path TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES conversion_jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_job_id
    ON chunks(job_id);

CREATE TABLE IF NOT EXISTS library_items (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    title TEXT,
    source_format TEXT,
    engine TEXT,
    voice TEXT,
    language TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS diagnostics_events (
    id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_diagnostics_events_correlation_id
    ON diagnostics_events(correlation_id);
