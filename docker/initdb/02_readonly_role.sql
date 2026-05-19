-- 02_readonly_role.sql -- runs once on first Postgres startup.
-- Creates a read-only role for the Postgres MCP server to connect with.
-- The application uses the read/write `earningsrag` superuser (default from
-- POSTGRES_USER); the MCP server must NEVER use that role. This file enforces
-- least-privilege at the database engine level, not just in app code.

-- Connect as superuser (the default when init scripts run).
\connect earningsrag

-- The role. Password matches what's in .env.example for local dev only.
-- Rotate this in production.
CREATE ROLE earningsrag_readonly WITH LOGIN PASSWORD 'earningsrag_readonly';

-- Connection access to the project DB.
GRANT CONNECT ON DATABASE earningsrag TO earningsrag_readonly;

-- Schema-level read access. `public` is the only schema in scope.
GRANT USAGE ON SCHEMA public TO earningsrag_readonly;

-- Read every current table.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO earningsrag_readonly;

-- Read every future table too. Without this line, a new table created later
-- would silently be invisible to the read-only role.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO earningsrag_readonly;

-- Sanity: never grant write. The MCP server should fail noisily on any
-- INSERT/UPDATE/DELETE/DDL it tries to run.
