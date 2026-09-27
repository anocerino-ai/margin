# Verification and acceptance checks

Run commands from the repository root after installing Python and Node dependencies. These checks are reproducible procedures, not a claim that every external service or deployment is continuously tested.

## Automated checks

```sh
.venv/bin/ruff check --config ruff.toml apps/api scripts
.venv/bin/pytest apps/api/tests -q
npm run build
npm run typecheck:bridge
.venv/bin/python scripts/export_contracts.py
npm run contracts
git diff --exit-code -- packages/contracts
.venv-docs/bin/mkdocs build --strict
```

A successful run exits with code zero for each command and leaves generated API contracts unchanged. Install documentation dependencies with `python3.12 -m venv .venv-docs` and `.venv-docs/bin/pip install -r requirements-docs.txt` before the last check.

Backend tests use fake providers to cover pipelines, queue ownership, login, independent connection updates, secret-free responses and English prompt selection. Run them from a full checkout: some checks inspect frontend source files that are not included in the production API image. Test counts can change as coverage grows.

## Container acceptance

```sh
docker compose up --build -d
docker compose ps -a
curl -fsS http://localhost:8080/api/auth/session
```

The initialization service should exit with code zero, API should be healthy, and web and worker should stay running. Auth status reports `configured: true` after administrator setup. An unauthenticated request to `/api/v1/settings` must return 401. Sign in through the UI and confirm the worker heartbeat and expected catalogs.

For D1, include `-f compose.yaml -f compose.d1.yaml` in every Compose command. Run `.venv/bin/python scripts/validate_bridge.py` after configuring the bridge. That probe verifies authentication rejection, parameter binding, schema presence, atomic rollback and lease constraints. It does not validate provider credentials.

## Controlled provider check

1. Save an OpenRouter key and enable a supported model. Use a small discovery limit.
2. Run discovery once; inspect source events, classification results and model attempts.
3. Save Firecrawl credentials, select a source and create an English draft.
4. Inspect the output and its source, model and prompt provenance.
5. Regenerate and confirm the old version remains available.
6. Enable an email digest only if you intend to send mail to the configured recipient; inspect its recorded outcome.

These actions consume provider quotas. Provider acceptance is not proof of factual accuracy or inbox delivery. Review generated text before approval or manual publication.

## Documentation deployment check

The Publish documentation workflow must complete both build and deploy jobs. Open the published homepage and at least one nested guide, check navigation and search, and confirm assets load under the repository path. A strict MkDocs build verifies internal links and navigation; it does not check availability of every external website.
