# Architecture

Margin separates its editorial interface from the code that processes sources. Vue 3, Vite and TypeScript render the workspace. FastAPI validates requests and coordinates Python services. A separate Python worker executes long-running jobs, while repository adapters store durable state in SQLite or Cloudflare D1.

## Request and job lifecycle

1. The browser sends an authenticated request through the same-origin web proxy.
2. FastAPI validates input and readiness, then creates the run and queue entry transactionally.
3. The worker claims an eligible job, assigns an owner and an expiry time, and refreshes its heartbeat while processing.
4. Each unit of work records progress and results in SQL. Writes are fenced by current lease ownership so a stale worker cannot overwrite a replacement worker's work.
5. The browser polls run details until a terminal state is reached. It does not wait for a single long HTTP request to finish generation.

The worker is a separate process, not a FastAPI background task. A server that sleeps or kills processes when there is no HTTP traffic can stop processing even when the dashboard remains available elsewhere.

## Discovery

Discovery snapshots active topics and reads enabled RSS feeds. URLs are normalized before deduplication. Only RSS titles enter classification; full source extraction is not part of discovery. OpenRouter returns structured data validated by Pydantic and semantic checks. Results distinguish target matches, non-target matches and failures.

Failures are recorded at source/article level so successful work remains usable. Known URLs are not automatically classified again in every run. Manual reclassification creates another recorded classification rather than silently rewriting history.

## Content generation

Selected articles become a generation run with source provenance. Firecrawl retrieves content or an eligible cached snapshot is reused. Context is checked against a character budget; oversized context fails instead of being silently truncated. There is no automatic summarization stage.

Blog and LinkedIn outputs have separate immutable versions. When generated together, LinkedIn depends on a particular blog version. Prompt name, version, hash, model attempts, source snapshots and dependencies allow reviewers to understand what produced a draft. New generation uses English v2 prompts. Markdown prompts are separate from Pydantic contracts; there is no LangGraph dependency.

## Persistence

SQLite provides a local single-host deployment. API and worker share the same file/volume. D1 provides shared remote SQL through an authenticated Cloudflare Worker whose `DB.batch` call groups statements atomically. The direct D1 REST adapter is separate and does not permit unrestricted multi-statement batches.

Local migrations live in `migrations/`; equivalent D1 migrations live in `infra/d1-migrations/`. The worker-guard trigger uses a `WHEN` condition in D1 for compatibility with Cloudflare's migration parser. Existing migration files must not be changed after application: add a numbered migration for schema changes.

## Authentication and secrets

One configured admin signs in using an email and password checked against a salted scrypt hash. Sessions are held in API memory for 12 hours and delivered as HttpOnly, SameSite=Strict cookies. Use one API process. A restart invalidates sessions, and a new login invalidates the previous session.

Provider overrides are stored in a restricted backend file and loaded for subsequent jobs. SQL holds configuration presence indirectly through application behavior, not the secret file itself. The API reports booleans, never stored key values. A deployment must provide persistent storage for UI-edited keys or use a different secret persistence design.

## Deployment boundaries

The web container publishes a loopback port; backend containers share an internal network. Netlify can serve the built frontend and proxy API requests to an external HTTPS service. D1 hosts data and a SQL bridge, not the Python API or its worker. GitHub Actions supplies scheduled wakeups and finite worker runs; it is not a continuously running application server.

Approval is an editorial state only. Margin does not automatically publish to external platforms.
