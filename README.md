# Margin

Discover engineering articles, classify them by topic, and turn selected sources into grounded English blog and LinkedIn drafts. Built with Vue 3, Vite, TypeScript and Python/FastAPI.

## Features

- RSS discovery and title-only classification, with deduplication and source-level failure tracking.
- Configurable OpenRouter model rotation and fallback.
- Firecrawl extraction only during content generation.
- Versioned Markdown prompts, immutable output history and source provenance.
- Single-admin login, no public registration, and individual provider settings.
- Durable SQL job queue and a separate worker. Human review before any publication.
- Docker Compose for a self-hosted workspace. SQLite storage or remote Cloudflare D1 through an authenticated Worker bridge.

## Prerequisites

| Requirement | Needed for | Setup |
| --- | --- | --- |
| Git | Cloning and publishing the repository | [Install Git](https://git-scm.com/downloads) |
| Docker Desktop, or Docker Engine with Compose | Running the complete container stack | [Docker Desktop](https://docs.docker.com/get-started/get-docker/) |
| Python 3.12 and pip/venv | Admin setup and local backend development | [Python downloads](https://www.python.org/downloads/) |
| Node.js >=22.12 and npm | Local frontend development and Cloudflare tooling; not required for container builds | [Node.js](https://nodejs.org/en/download) |
| OpenRouter account and API key | Classification and content generation | [Create a key](https://openrouter.ai/keys) |
| Firecrawl account and API key | Extracting source content during generation | [Firecrawl dashboard](https://www.firecrawl.dev/app) |
| Resend account and sending key | Optional email digests | [Resend API keys](https://resend.com/api-keys) |
| GitHub account | Publishing the repository and scheduled workflows | [GitHub signup](https://github.com/signup) |
| Cloudflare account | Optional remote D1 persistence and Worker bridge | [Cloudflare signup](https://dash.cloudflare.com/sign-up) |

Start Docker Desktop before running Compose. Ports 8080 (Docker UI), or 5173 and 8000 (local development), must be available. Internet access is required for initial builds, RSS feeds and provider calls. Local manual discovery works without GitHub or Cloudflare. Provider free tiers have their own limits; check your account dashboards before running large jobs.

## Quick start with Docker

Requirements: Docker Desktop or Docker Engine with Compose, Python 3.12 for the local admin setup below.

```sh
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
.venv/bin/pip install --no-deps -e apps/api
.venv/bin/python scripts/admin.py
docker compose up --build -d
```

Do not overwrite an existing `.env`. The admin script asks for your email and password and stores only a password hash. Open http://localhost:8080 and sign in. Add each provider key separately under Settings → Connections. Configure model IDs with structured output support, then run discovery manually.

Compose starts initialization, API, worker and the web server. The `workspace` volume persists the database and provider overrides. Docker data is separate from your local development database. `docker compose down` preserves data; `down -v` deletes the volume.

## Configure the administrator

There is **no default email or password** and no public registration. Create your own single administrator before signing in. With the Python environment installed as described above, run this command from the repository root:

```sh
.venv/bin/python scripts/admin.py
```

1. Enter your admin email.
2. Enter a password with at least **12 characters**. Password input is hidden in the terminal.
3. Repeat the password to confirm it.

The script stores `MARGIN_ADMIN_EMAIL` and a salted scrypt hash in `MARGIN_ADMIN_PASSWORD_HASH` in your local `.env`. It does not store the plaintext password. Keep `.env` private and do not paste the plaintext password into the hash setting.

For a first Docker startup, continue with `docker compose up --build -d`. If the containers already exist, reload the updated credentials with:

```sh
docker compose up -d --force-recreate api worker
```

Then open http://localhost:8080 and sign in with the email and password you chose. A plain `docker compose restart` does not reload environment variables from `.env`.

For local development, stop `scripts/dev.py` with Ctrl-C and start it again. To change or reset forgotten credentials later, rerun the same admin script and recreate/restart the appropriate services. Existing API sessions are invalidated when the API restarts; articles and generations are preserved.


## Local development

Requires Node >=22.12 and the Python environment above.

```sh
npm ci
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/dev.py
```

Open http://127.0.0.1:5173. Restart the services after changing admin credentials or `.env`. Provider changes saved in the UI apply to subsequent jobs without a restart. Each connection has its own Edit, Save and Cancel actions; saved secrets are never returned to the browser. Configured means a value exists, not that the provider has been tested.

## Configure connections

1. Sign in and open **Settings → Connections**.
2. For **OpenRouter**, create a key in [API Keys](https://openrouter.ai/keys), paste it into its field and click **Save**. Add at least one enabled model ID under model settings. Choose a model supporting structured output; use the [model catalog](https://openrouter.ai/models) to check current availability and pricing.
3. For **Firecrawl**, copy your key from the [dashboard](https://www.firecrawl.dev/app), then save that connection. It is used only when generating content, not during RSS discovery. See [the introduction](https://docs.firecrawl.dev/introduction).
4. For **Resend**, create a key with **Sending access** and save it. Full account access is unnecessary for sending digests. See [API key permissions](https://resend.com/docs/dashboard/api-keys/introduction).
5. Set **Sender email** and **Recipient email** separately. For initial Resend tests use `Margin <onboarding@resend.dev>` and your Resend signup email. To send to other recipients, [verify your own domain](https://resend.com/docs/dashboard/domains/introduction) and use a sender on that domain.
6. Enable the digest in runtime settings only when you want discovery emails.

Configured connections show a disabled field with fixed masking dots and **Edit**. Editing starts with an empty field: existing secrets are never sent to the browser. Unconfigured fields are immediately editable. Each **Save** changes only that connection. “Configured” indicates presence, not a successful external API test.

Provider overrides are stored in `data/providers.json` locally or the Docker volume. Existing `.env` values remain fallback configuration. Never commit either secrets file. Changes made through the UI do not update GitHub Actions secrets automatically.

## Container operations

```sh
docker compose ps
docker compose logs --tail=100 api worker
docker compose restart api worker
docker compose down
```

Use `docker compose up --build -d` after code changes. After `.env` changes, use `docker compose up -d --force-recreate`; a plain restart does not reload container environment variables. The one-shot `init` service is expected to exit successfully, while API, worker and web remain running. Avoid `down -v`: it deletes persistent data. Before migrating or upgrading, stop writers and back up the volume.

## Repository and remote automation

Follow the [GitHub repository guide](docs/github.md), then the [Cloudflare D1 guide](docs/cloudflare.md), and finally the [GitHub Actions guide](docs/github-actions.md). The scheduler and dashboard share the same D1 database.

## Workflow

1. Configure sources, topics and OpenRouter models.
2. Run discovery to populate the library. Discovery does not use Firecrawl.
3. Select articles and generate an English blog, LinkedIn draft, or both.
4. Review sources and version history, regenerate if needed, and approve a draft.

The application does not publish content automatically. Provider calls consume your provider quotas. Resend test sending requires its onboarding sender and your account email until you verify a domain.

## Repository

- `apps/web`: editorial UI and authenticated API client.
- `apps/api`: routes, schemas, services, SQL adapters and providers.
- `prompts`: versioned Markdown prompts, separate from Pydantic schemas.
- `migrations`: SQL schema and queue migrations.
- `config`: initial verified RSS sources and topics.
- `packages/contracts`: generated OpenAPI and TypeScript contracts.
- `infra`: container configuration and the D1 bridge.

New content uses English `v2` prompts. Legacy `v1` files remain for historical provenance; existing drafts are not rewritten.

## Verification

```sh
.venv/bin/pytest apps/api/tests -q
.venv/bin/ruff check apps/api scripts
npm run build
npm run typecheck:bridge
.venv/bin/python scripts/export_contracts.py
npm run contracts
```

Automated provider tests use fakes. Container and live-provider checks are tracked separately in [verification](docs/verification.md).

## Hosting and security

See [deployment options](docs/deployment.md), [setup](docs/setup.md), [security](SECURITY.md) and [contributing](CONTRIBUTING.md). Never commit `.env`, provider overrides, databases or credentials. Remote deployments need HTTPS, secure cookies and volume backups. The current session store supports one API process and expires sessions after 12 hours or a restart.

Scheduled discovery uses GitHub Actions to evaluate the saved schedule against the shared D1 database. Use the manual discovery action for on-demand runs.

Licensed under MIT.

## Documentation site

Detailed English documentation is maintained with MkDocs: installation, admin login, provider setup, daily workflows, environment reference, backups, troubleshooting, API, architecture and remote deployment.

```sh
python3.12 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve
```

Open http://127.0.0.1:8001. Build with `.venv-docs/bin/mkdocs build --strict`; CI validates documentation on pushes and pull requests. This does not publish a public site. See [documentation development](docs/documentation.md).
