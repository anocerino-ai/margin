# D1 validation

The Worker bridge authenticates each batch and uses Cloudflare DB.batch for transactional execution. The local SQLite schema and D1 schema use equivalent constraints. D1 migrations use a `WHEN` trigger instead of a `CASE` expression so the migration parser handles the trigger body correctly.

Run `.venv/bin/python scripts/validate_bridge.py` against the configured bridge. It checks authentication, parameter binding, required tables, rollback after a duplicate key, and invalid lease rejection. Probe records are isolated in a randomly named table and cleaned up.

Apply migrations before connecting API and worker. Preserve migration history: add new numbered migrations to both SQL backends rather than changing already-applied files. For queue or versioning changes, extend tests for ownership fencing, dependencies, concurrency and restart recovery.

A successful probe verifies these specific database properties; it does not test provider credentials, every workload or a complete content-generation run.
