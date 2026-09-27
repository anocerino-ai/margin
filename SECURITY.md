# Security

Do not report vulnerabilities with working credentials or private data in public issues. Until a private reporting channel is configured, use the hosting platform's private vulnerability reporting feature where available.

The workspace is single-admin. Sessions are kept in one API process and expire after 12 hours; restarting the API invalidates them. Use HTTPS and `MARGIN_COOKIE_SECURE=true` for remote deployment. Do not run multiple API replicas with the current session store.

Provider overrides are stored as plaintext in a restricted backend file, not returned through the API. Protect and encrypt host storage and backups. Only the web container exposes a local port by default. Never expose Vite as a production server.
