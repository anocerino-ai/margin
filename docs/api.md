# API

OpenAPI is generated in `packages/contracts/openapi.json`. Auth routes: POST `/api/auth/login`, GET `/api/auth/session`, POST `/api/auth/logout`. Protected workspace endpoints use `/api/v1` and an HttpOnly session cookie. Mutations require `X-Requested-With: Margin`.

PUT `/api/v1/settings/providers` updates only nonempty provider values. It returns a saved flag, never credentials. GET `/api/v1/system/status` reports configuration presence, not validity. Runtime settings, sources, topics, discovery runs and generation versions have separate endpoints in the generated contract.
