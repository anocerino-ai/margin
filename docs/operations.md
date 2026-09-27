# Docker operations and backups

## Services

| Service | Responsibility | Expected state |
| --- | --- | --- |
| init | Apply migrations and seed SQLite catalogs; check remote schema in the D1 profile | Exited with code 0 |
| api | HTTP routes, login, validation and queue submission | Healthy |
| worker | Lease/execute jobs and persist results | Running |
| web | Serve built Vue files and proxy `/api` | Running |

API and worker share the `workspace` volume. The Compose project name depends on the checkout directory unless explicitly overridden. Renaming that directory or changing the project name can select a different volume; preserve the existing name or migrate storage intentionally.

## Lifecycle

```sh
docker compose ps -a
docker compose logs --tail=100 api worker
docker compose up --build -d
docker compose down
```

Build again after code changes. After `.env` changes, recreate containers with `docker compose up -d --force-recreate`. A restart alone retains their original environment. UI provider updates are read for subsequent jobs without rebuilding.

`down` preserves the volume; **`down -v` deletes it**. Never use the latter as a troubleshooting shortcut on a workspace containing content.

## Backup strategy

Back up both the SQL database and `providers.json`, plus the private host `.env` holding admin configuration. Backups contain credentials and must be protected like the live deployment.

1. Pause new work and wait for running jobs, or record which jobs may need recovery.
2. Stop API and worker to stop writes.
3. Identify the actual named volume with `docker volume ls` and the Compose project label. Use Docker's volume backup tooling or an approved backup container to archive the full volume, not just an open database file.
4. Store the archive and `.env` securely, outside the repository.
5. Restart the services and verify health and worker heartbeat.

Test restores into a separate Compose project and volume. Do not overwrite your only copy to test recovery. SQLite write-ahead/journal files, if present, belong with the stopped database snapshot.

## Updates and rollback

Review migration changes before pulling updates. Back up first, rebuild, inspect init exit status and API health, then sign in and inspect a known article. Container image rollback alone does not reverse schema changes. Restore a compatible backup when a migration is not backward-compatible.

## Health boundaries

`/health` confirms the HTTP process responds; it does not prove provider credentials work. Worker heartbeat indicates recent activity, not that every queued job succeeded. Check run events and output state for pipeline outcomes.

## D1 deployment profile

For remote persistence, include both files in every lifecycle command:

```sh
docker compose -f compose.yaml -f compose.d1.yaml up -d
docker compose -f compose.yaml -f compose.d1.yaml ps
```

D1 contains the application records; the Docker volume still holds local provider overrides. Back up remote records using Cloudflare D1 export/Time Travel, and protect the local credentials volume separately. Default Compose without the override selects local SQLite.

## Automatic resumption after a quota pause

In **Settings**, **Automatically resume queued work after the daily quota resets** is enabled by default. Save runtime settings after changing it. This setting is stored in SQL and applies to workers without restarting containers.

When enabled, queued work resumes after the displayed quota reset time, provided the worker is running. When disabled, quota-paused work remains held even after that time. Enable the option and save to release the hold once the reset time has passed. Turning it on early does not bypass the quota. Turning it off does not cancel a running request or disable ordinary discovery scheduling; it controls resumption after quota exhaustion.

The existing job continues from saved progress. Completed classifications and generated versions are preserved. This is not a fresh discovery of every feed and does not automatically retry old terminal failures. The dashboard explains whether resumption is automatic or disabled. The built-in worker handles resumption; no Codex automation is required.
