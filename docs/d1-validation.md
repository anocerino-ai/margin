# D1 validation

The Worker bridge authenticates each batch and uses Cloudflare DB.batch for transactional execution. The local SQLite schema and D1 schema use equivalent constraints. D1 migrations use a `WHEN` trigger instead of a `CASE` expression so the migration parser handles the trigger body correctly.

Run `.venv/bin/python scripts/validate_bridge.py` against the configured bridge. It checks authentication, parameter binding, required tables, rollback after a duplicate key, and invalid lease rejection. Probe records are isolated in a randomly named table and cleaned up.

Apply migrations before connecting API and worker. Preserve migration history: add new numbered migrations to both SQL backends rather than changing already-applied files. For queue or versioning changes, extend tests for ownership fencing, dependencies, concurrency and restart recovery.

A successful probe verifies these specific database properties; it does not test provider credentials, every workload or a complete content-generation run.

## Prerequisites and execution

Use a Python environment with the application dependencies installed. The remote database must have all committed D1 migrations applied. In your private `.env`, set `MARGIN_D1_WORKER_URL` to the deployed HTTPS base URL and `MARGIN_D1_WORKER_TOKEN` to the same value as the Worker’s `BRIDGE_TOKEN` secret.

```sh
.venv/bin/python scripts/validate_bridge.py
```

Run the probe from the repository root with access to the target database. A failure should be investigated before starting new jobs: check the URL, matching token, applied migrations and Cloudflare service status. Do not resolve a probe failure by dropping application tables or deleting the local volume.

## What to check after switching storage

Start API and worker with the same D1 profile, sign in, and inspect the source, topic and model catalogs. A newly created database is empty; migration success does not imply that local records were copied. Confirm the worker heartbeat before submitting a small manual discovery. Inspect its recorded result and verify that refreshing the page reads the same persisted data.

The direct REST probe `scripts/validate_d1.py` targets a different adapter using Cloudflare account credentials. Its result does not replace bridge validation for a deployment configured with `MARGIN_STORAGE=d1_worker`.
