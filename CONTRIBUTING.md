# Contributing

Start with an issue describing the problem and expected behavior. Keep changes focused and include regression tests for behavior changes. Never commit credentials, personal data, generated databases or provider responses containing private data.

Checks: `pytest apps/api/tests -q`, `ruff check --config ruff.toml apps/api scripts`, `npm run build`, `npm run typecheck:bridge`. Regenerate API contracts after changing endpoints. Provider integrations should be tested with fakes by default; document any live checks separately.
