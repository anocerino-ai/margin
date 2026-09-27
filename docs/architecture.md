# Architecture

Vue renders the editorial workspace; FastAPI owns authentication, validation and use cases. Repository adapters isolate SQL persistence. SQLite is the local default. The D1 Worker bridge executes authenticated atomic batches. Local migrations live in `migrations/`; equivalent D1 migrations live in `infra/d1-migrations/`, using a trigger syntax compatible with Cloudflare migration parsing.

Discovery reads RSS and classifies titles using a topic snapshot. Generation extracts selected content through Firecrawl and calls OpenRouter. Model attempts, source snapshots, prompt versions, hashes and output dependencies are persisted. No LangGraph is used.

The queue worker claims jobs with a lease and fences writes by ownership. HTTP requests enqueue long-running work. The UI polls progress. Provider overrides are read before subsequent jobs and stored outside the repository. Sessions use HttpOnly same-site cookies; mutation requests require a custom CSRF header. One API process is supported.

Compose shares a persistent local volume between the API and worker, with Nginx as the only published port. All content requires manual review; there is no automatic publishing integration.
