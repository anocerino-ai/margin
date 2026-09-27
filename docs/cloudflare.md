# Cloudflare D1 and Worker bridge

The authenticated Worker bridge connects the Python API and job worker to a shared D1 SQL database. Run these commands to provision a deployment in your Cloudflare account.

## Requirements

A [Cloudflare account](https://dash.cloudflare.com/sign-up), Node >=22.12, `npm ci`, the project Python environment, and a tested local workspace. You do not need to transfer your existing domain to use a `workers.dev` endpoint. Follow [Cloudflare's D1 guide](https://developers.cloudflare.com/d1/get-started/) for dashboard navigation.

## Create and configure

From the repository root:

```sh
npx wrangler login
npx wrangler d1 create margin --config infra/d1-worker/wrangler.jsonc
```

Copy the returned database ID into `.env` as `MARGIN_D1_DATABASE_ID`, then run:

```sh
.venv/bin/python scripts/setup_remote.py
npx wrangler d1 migrations apply margin --remote --config infra/d1-worker/wrangler.jsonc
npx wrangler deploy --config infra/d1-worker/wrangler.jsonc
npx wrangler secret put BRIDGE_TOKEN --config infra/d1-worker/wrangler.jsonc
```

The setup script generates `MARGIN_D1_WORKER_TOKEN` privately in `.env`. Enter that exact value at Wrangler's secret prompt; do not place it in a command argument, screenshot, commit or chat. The Worker rejects requests until its secret is configured. Record the deployed HTTPS URL as `MARGIN_D1_WORKER_URL` (base URL, without `/batch`).

## Validate before switching

Run the remote probe after saving the URL and token:

```sh
.venv/bin/python scripts/validate_bridge.py
```

The probe verifies unauthorized access rejection, parameter binding, atomic rollback on a constraint failure, required tables and rejection of invalid worker leases. It creates and removes a temporary probe table. The separate `validate_d1.py` checks the direct REST adapter, not this bridge.

To connect Docker:

```sh
docker compose -f compose.yaml -f compose.d1.yaml up -d --force-recreate
```

Use both Compose files for subsequent operations. The override selects `d1_worker` for API and worker, and replaces local initialization with a remote-schema check. The local volume is retained for provider overrides and as a backup of local SQLite data. Running only the default Compose file selects SQLite again. For non-Docker development, set `MARGIN_STORAGE=d1_worker` and restart the services.

The remote database starts empty. Configure topics, sources and models through the authenticated API/UI after switching. Existing local articles and generations are not copied automatically. Configure runtime schedule settings on the remote database and keep the original local volume as a backup.

The Worker token grants backend SQL access: protect it like a database password. Cloudflare hosts persistence and this bridge; it does not deploy the Python API, durable worker or frontend automatically.
