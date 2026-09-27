# Security

Do not report vulnerabilities with working credentials or private data in public issues. Until a private reporting channel is configured, use the hosting platform's private vulnerability reporting feature where available.

The workspace is single-admin. Sessions are kept in one API process and expire after 12 hours; restarting the API invalidates them. Use HTTPS and `MARGIN_COOKIE_SECURE=true` for remote deployment. Do not run multiple API replicas with the current session store.

Provider overrides are stored as plaintext in a restricted backend file, not returned through the API. Protect and encrypt host storage and backups. Only the web container exposes a local port by default. Never expose Vite as a production server.

## Deployment checklist

- Use one API process while sessions remain in memory.
- Terminate HTTPS before remote traffic and enable secure cookies.
- Keep backend provider files and backups off public/static hosting.
- Do not expose the D1 SQL bridge without its token.
- Keep `.env`, local databases and `data/` ignored by Git.
- Review provider spending limits and rotate any exposed keys.

The application stores provider overrides with restrictive file permissions, not application-level encryption. Docker users and host administrators can access container environments and volumes. Login protects application routes, not the host machine.
