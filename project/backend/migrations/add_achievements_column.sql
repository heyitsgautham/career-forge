-- Migration: Add achievements column to users table
-- Date: 2026-03-07
-- Format: [{"title": str, "issuer": str, "date": str, "description": str}]

ALTER TABLE users ADD COLUMN IF NOT EXISTS achievements JSON;
