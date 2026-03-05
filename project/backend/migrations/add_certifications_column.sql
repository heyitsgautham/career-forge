-- Add certifications column to users table
-- This stores certification data as JSON array
-- Format: [{"name": str, "issuer": str, "date": str, "credential_id": str, "url": str}]

ALTER TABLE users ADD COLUMN certifications TEXT;
