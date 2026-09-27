# Developer workflow

Use Python 3.12 and Node >=22.12. Install the locked dependencies as described in [installation](installation.md). Python code lives in `apps/api/src/margin`; UI code lives in `apps/web/src`. Keep business logic in Python services and external integrations behind provider adapters.

## Checks matching CI

```sh
.venv/bin/ruff check --config ruff.toml apps/api scripts
.venv/bin/pytest apps/api/tests -q
npm ci
npm run build
npm run typecheck:bridge
.venv/bin/python scripts/export_contracts.py
npm run contracts
git diff --exit-code -- packages/contracts
```

Ruff's explicit first-party declaration for `margin` keeps import sorting consistent across working directories and CI. Do not weaken lint selection to hide import errors.

Generated API contracts must be committed alongside route/schema changes. Provider tests should use fakes by default; explicitly distinguish live checks that consume quotas or send messages. Never put real keys in test fixtures.

## Migrations and prompts

Add a new numbered migration instead of modifying a migration already applied to a persistent database. Migration checksums protect history. Test constraints, rollback and worker recovery when changing queue behavior.

Create a new prompt version when changing generated behavior. Keep Markdown separate from Pydantic schemas, update the selected prompt version and ensure stored provenance agrees with the actual prompt/hash. Current blog and LinkedIn generation use English v2; classification uses v1.

## Documentation changes

Follow [documentation development](documentation.md). Every new operator-facing setting or behavior should have a documented default, scope and restart requirement. Mark unvalidated deployment paths clearly.
