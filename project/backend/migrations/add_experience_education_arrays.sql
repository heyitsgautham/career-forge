-- Migration: Add experience and education arrays to users table
-- Date: 2025-12-18

-- Add experience column (JSON array)
ALTER TABLE users ADD COLUMN IF NOT EXISTS experience JSONB;

-- Add education column (JSON array)
ALTER TABLE users ADD COLUMN IF NOT EXISTS education JSONB;

-- Add comments for documentation
COMMENT ON COLUMN users.experience IS 'Array of work experience entries: [{company, title, dates, location, highlights}]';
COMMENT ON COLUMN users.education IS 'Array of education entries: [{school, degree, field, dates, location, gpa}]';
