# HTTP API

Margin exposes JSON routes under `/api`. A same-origin reverse proxy sends frontend calls to FastAPI. In development the API listens on port 8000; Docker exposes only the web server on port 8080.

## Authentication

POST `/api/auth/login` accepts `{"email":"admin@example.com","password":"your password"}`. A successful response sets an HttpOnly session cookie; do not store a separate bearer token in the browser. GET `/api/auth/session` reports authentication and admin configuration. POST `/api/auth/logout` clears the session.

All `/api/v1` routes require a session. State-changing requests must include `X-Requested-With: Margin`. This header alone is not authentication: the session cookie is also required. Use JSON Content-Type for request bodies. Login is throttled after ten attempts within one minute.

## Errors and pagination

Errors use `{"error":{"code":"…","message":"…","details":{}}}`. Typical statuses are 401 for missing sessions, 403 for invalid mutation headers, 404 for missing resources, 409 for conflicting state and 422 for input/readiness failures. Clients should show the message without assuming every non-target article is an error.

List endpoints expose `items` and `pagination`. Page numbers begin at 1; page size is bounded to 100. Article filtering supports source, classification, topic, date range and run. Results must be consumed from the API rather than inferred from UI counters.

## Long-running operations

Creating a discovery or generation enqueues work. An accepted request is not proof that the operation completed. Poll the returned run's detail route for progress, errors and resulting versions. A separate worker must be online. Retry only after inspecting existing run state to avoid unintentional duplicate work.

## Connection settings

GET `/api/v1/settings/providers` returns boolean flags for each supported field. PUT on the same route accepts any subset of `openrouter_api_key`, `firecrawl_api_key`, `resend_api_key`, `email_from` and `email_recipient`. Only nonempty submitted values are replaced. A saved response does not echo secrets. GET `/api/v1/system/status` reports readiness indicators and worker heartbeat; it does not contact each provider to validate credentials.

## Route inventory

The following inventory is derived from the committed OpenAPI contract. Interactive Swagger is available at `/docs` on the API server; its documentation is not a substitute for authentication on protected operations.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/session` | Session |
| POST | `/api/auth/logout` | Logout |
| GET | `/health` | Health |
| GET | `/api/v1/dashboard/summary` | Summary |
| GET | `/api/v1/topics` | Topics |
| POST | `/api/v1/topics` | Create Topic |
| PATCH | `/api/v1/topics/{id}` | Update Topic |
| GET | `/api/v1/sources` | Sources |
| POST | `/api/v1/sources` | Create Source |
| PATCH | `/api/v1/sources/{id}` | Update Source |
| GET | `/api/v1/articles` | Articles |
| GET | `/api/v1/articles/{id}` | Article |
| GET | `/api/v1/classification-runs` | Runs |
| POST | `/api/v1/classification-runs` | Request Discovery |
| GET | `/api/v1/classification-runs/{id}` | Run |
| GET | `/api/v1/generations` | Generations |
| POST | `/api/v1/generations` | Create Generation |
| GET | `/api/v1/generations/{id}` | Generation |
| GET | `/api/v1/generations/{id}/sources` | Generation Sources |
| GET | `/api/v1/generations/{id}/outputs` | Generation Outputs |
| GET | `/api/v1/generation-outputs/{id}/versions/{version}` | Generation Version |
| POST | `/api/v1/generation-outputs/{id}/versions/{version}/approve` | Approve |
| GET | `/api/v1/settings` | Get Settings |
| PUT | `/api/v1/settings` | Put Settings |
| PATCH | `/api/v1/settings` | Patch Settings |
| PATCH | `/api/v1/settings/llm-models/{id}` | Update Model |
| DELETE | `/api/v1/settings/llm-models/{id}` | Delete Model |
| GET | `/api/v1/settings/llm-models` | Models |
| POST | `/api/v1/settings/llm-models` | Add Model |
| POST | `/api/v1/generation-outputs/{id}/versions` | Regenerate |
| POST | `/api/v1/articles/{id}/classification/retry` | Retry Classification |
| GET | `/api/v1/emails` | Emails |
| POST | `/api/v1/emails/{id}/retry` | Retry Email |
| POST | `/api/v1/sources/test` | Test Feed |
| GET | `/api/v1/system/status` | System Status |
| POST | `/api/v1/settings/llm-models/reorder` | Reorder |
| GET | `/api/v1/settings/providers` | Provider Status |
| PUT | `/api/v1/settings/providers` | Update Providers |

## Version and approval behavior

Generation outputs contain version history and dependencies. Regeneration preserves existing versions and creates a new one from recorded source context. Approval changes review state; it does not send a post to LinkedIn or publish a blog. Dependent output versions keep the exact blog version they used.

## Updating clients

The repository stores `packages/contracts/openapi.json` and generated TypeScript types. When routes or schemas change, run `.venv/bin/python scripts/export_contracts.py` and `npm run contracts`, commit both files and verify the UI against the changed response shape. Never add real credentials or session cookies to example requests.

## Quota configuration and status

Runtime settings include `openrouter_requests_per_minute` (default 20), `openrouter_requests_per_day` (default 50), and `openrouter_auto_resume` (default true). GET/PUT/PATCH `/api/v1/settings` exposes these fields to authenticated administrators. GET `/api/v1/system/status` returns `quota_pause`, either null or an object containing `until` (Unix seconds), `reason` and `auto_resume`. A hold with auto-resume disabled remains visible after its timestamp. Enable auto-resume through Settings to release it after the quota window.
