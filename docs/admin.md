# Administrator login

Margin has one server-configured administrator. There is no default password, public registration, invitation flow or email password-reset service.

## Create or reset credentials

From the project root, using the installed Python environment:

```sh
.venv/bin/python scripts/admin.py
```

Enter your email, a password of at least 12 characters, and repeat it. Password input is hidden. The script writes `MARGIN_ADMIN_EMAIL` and `MARGIN_ADMIN_PASSWORD_HASH` to `.env`; the password is stored as a salted scrypt hash, never as plaintext. Do not enter a plaintext password into the hash field.

## Apply changes

For existing Docker containers using SQLite:

```sh
docker compose up -d --force-recreate api worker
```

For D1, use `docker compose -f compose.yaml -f compose.d1.yaml up -d --force-recreate api worker` instead, preserving the selected storage profile.

A plain container restart retains the old environment. For local development, stop and rerun `scripts/dev.py`. Sign in at the URL for the deployment you restarted.

To recover a forgotten password, run the same script again on the host. Existing content stays in the database. Recreating/restarting the API invalidates current sessions.

## Session behavior

Sessions are held in API memory and expire after 12 hours. Login creates an HttpOnly, SameSite=Strict cookie. The current implementation permits one active session: a new successful login clears older sessions. Use one API process; multiple replicas cannot share the in-memory session store.

Ten login attempts within a minute trigger throttling. This limit is process-wide, not per-account or per-client. Mutating workspace requests also require the application's custom request header. Use HTTPS and `MARGIN_COOKIE_SECURE=true` for remote access.

The health and auth-status endpoints remain accessible without a session. Workspace data and settings require login. See [security](security.md) for deployment boundaries.

## Session expiry in the browser

When a workspace request returns HTTP 401, the application closes the workspace and opens the login page with a session-expired message. This applies to page loads, polling and save actions. Sign in again to return to Overview. Unsaved edits are not submitted again automatically. Network errors and HTTP 403 responses do not trigger this redirect.
