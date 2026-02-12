-- Add source_format column to documents table for AC3 compliance
ALTER TABLE documents ADD COLUMN source_format TEXT;
