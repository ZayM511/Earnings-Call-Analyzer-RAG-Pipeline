-- 01_extensions.sql -- runs once on first Postgres startup (FIRST run only).
-- Enables pgvector for VECTOR(n) columns and the cosine distance operator,
-- and pg_trgm for trigram-based fuzzy text matching (used for company-name
-- normalization where transcripts spell out the company a few different ways).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
