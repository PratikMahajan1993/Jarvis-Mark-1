-- Description: what this migration does
-- Dependencies: migration numbers this script assumes are already applied
--
-- The migration runner splits on ';' and executes each statement. Do not wrap
-- the file in BEGIN/COMMIT — a connection may already be inside a transaction,
-- and SQLite commits DDL implicitly. Keep the script forward-only and idempotent
-- (INSERT OR IGNORE, or ALTER that tolerates a duplicate column).

-- idempotent inserts/updates go here
