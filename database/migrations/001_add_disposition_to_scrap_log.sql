-- Migration 001: Add disposition column to scrap_log
-- This column was referenced by api_quality.py and api_workorders.py but missing from schema
ALTER TABLE scrap_log ADD COLUMN disposition TEXT;
