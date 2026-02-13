-- Add source_format column to documents table
-- This field is used throughout the codebase to track document format (epub, pdf, txt, md)

ALTER TABLE documents ADD COLUMN source_format TEXT;
