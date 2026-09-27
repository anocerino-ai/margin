# End-to-end setup

This page describes a complete path from a checkout to a usable local workspace, then a shared remote database. Commands are run from the repository root. Never overwrite an existing `.env` or delete a data volume as part of setup.

## Local workspace

Install Git, Python 3.12, Docker Desktop and Compose. Start the Docker engine, then:

```sh
git clone https://github.com/anocerino-ai/margin.git
cd margin
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
.venv/bin/pip install --no-deps -e apps/api
.venv/bin/python scripts/admin.py
docker compose up --build -d
```

Enter your admin email and a password of at least 12 characters when prompted. Open http://localhost:8080 and sign in. There is no registration screen or default password.

In Settings, save OpenRouter and Firecrawl keys individually. Add at least one enabled OpenRouter model with structured-output support. For email digests, add a Resend sending key, sender and recipient, then enable email in runtime settings. The onboarding sender `Margin <onboarding@resend.dev>` can send test mail only to your Resend signup email; other recipients require a verified domain.

Run discovery manually. It reads RSS titles and populates the library. Select articles, request a blog/LinkedIn generation, inspect source provenance and approve only after review.

## Use shared D1 storage

Install Node >=22.12 and run `npm ci`. Authenticate with `npx wrangler login`. Create a database, put its ID into `.env` as `MARGIN_D1_DATABASE_ID`, and prepare the bridge:

```sh
npx wrangler d1 create margin --config infra/d1-worker/wrangler.jsonc
.venv/bin/python scripts/setup_remote.py
npx wrangler d1 migrations apply margin --remote --config infra/d1-worker/wrangler.jsonc
npx wrangler deploy --config infra/d1-worker/wrangler.jsonc
npx wrangler secret put BRIDGE_TOKEN --config infra/d1-worker/wrangler.jsonc
```

At the secret prompt, enter the generated `MARGIN_D1_WORKER_TOKEN` from your private `.env`. Save the deployed base URL as `MARGIN_D1_WORKER_URL`, then run `.venv/bin/python scripts/validate_bridge.py`. Cloudflare may ask you to register an available workers.dev subdomain during first deployment.

Start the remote profile with `docker compose -f compose.yaml -f compose.d1.yaml up -d --force-recreate`. Both API and worker now use D1. A new remote database does not automatically contain local records: configure sources, topics and models or perform a reviewed migration. Preserve the original local volume.

## Scheduled discovery

In GitHub repository Settings → Secrets and variables → Actions, add bridge/provider secrets and the bridge URL/sender variables. Set `MARGIN_SCHEDULE_ENABLED=true` only when the remote catalogs and desired runtime schedule are configured. The workflow checks hourly whether a slot is due and records processed slots to avoid duplication.

GitHub Secrets do not synchronize with UI changes. Update them separately when rotating provider keys. The dashboard and Python API still need hosting; scheduled Actions do not serve either application.
