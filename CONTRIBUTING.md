# Contributing to Margin

Margin is a single-admin editorial workspace built with Vue, FastAPI and a durable SQL job queue. Discuss substantial behavior changes in an issue before implementing them. For a focused bug fix, include a reproducible example and the expected result in the pull request.

## Development setup

Use Python 3.12 and Node.js 22.12 or newer. From a checkout:

```sh
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
.venv/bin/pip install --no-deps -e apps/api
npm ci
.venv/bin/python scripts/admin.py
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/dev.py
```

Copy `.env.example` only on first setup. Open http://127.0.0.1:5173 and sign in with your configured credentials. External operations require your own provider keys; tests use fakes.

## Validate a change

```sh
.venv/bin/ruff check --config ruff.toml apps/api scripts
.venv/bin/pytest apps/api/tests -q
npm run build
npm run typecheck:bridge
```

After API changes, run `.venv/bin/python scripts/export_contracts.py` and `npm run contracts`, then include the generated contract changes. For documentation, install `requirements-docs.txt` in a separate environment and run `mkdocs build --strict`.

## Design conventions

Keep business logic in Python services and integrations behind provider interfaces. Preserve the difference between failed classification and a valid non-target result. Add numbered migrations for schema changes rather than editing applied migrations. Version prompts rather than overwriting prompts referenced by existing outputs.

Keep UI copy, documentation and active generation prompts in English. Document new settings with their default, persistence location and restart behavior. Add regression coverage for meaningful behavior changes; do not call live providers in automated tests.

## Pull requests

Use a focused branch. Explain the problem, final behavior and checks performed. Include screenshots for visible UI changes after removing personal data. Keep unrelated formatting and generated data out of the diff. Never commit credentials, cookies, provider responses containing private data or local databases.

Report vulnerabilities through the repository's private reporting channel described in [SECURITY.md](SECURITY.md), not a public issue.
