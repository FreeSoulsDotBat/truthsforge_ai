CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS app_metadata (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_metadata (key, value)
VALUES ('schema_bootstrap', '{"version":"0.1.0","owner":"truths-forge-ai"}')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
