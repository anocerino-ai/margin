# Verification

Validated on macOS Apple Silicon with Docker Engine 29.8.0 and Compose 5.5.1:

- `docker compose up --build -d` builds and starts the stack successfully.
- The initialization service exits with code 0; API is healthy; web and worker remain running.
- Nginx serves the frontend at localhost:8080 and proxies API requests.
- The auth session endpoint reports an admin is configured. Protected endpoints return 401 without a session.
- The persistent database contains five initial sources and a worker heartbeat.
- All 21 backend tests pass both locally and inside the Linux API image, with real provider credentials excluded from the test environment.
- Frontend type checking and production builds pass locally and inside Docker.

Tests cover independent provider updates, secret-free status responses, login/logout, password hashing, session protection, English generation prompts, queue fencing and pipeline behavior with fake providers.

Remote D1 checks verify authentication rejection, parameter binding, table availability, atomic rollback and invalid-lease rejection. Use `scripts/validate_bridge.py` to repeat them. API health and worker heartbeat can be checked independently of provider calls.

These checks do not certify external-provider output quality or email delivery. Run a controlled discovery and generation with your configured providers when validating those integrations. Docker and development storage are selected by deployment configuration.
