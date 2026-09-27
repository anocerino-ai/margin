# Deployment options

## Netlify frontend + separate backend

Build from the repository root: `npm ci && npm run build`; publish `apps/web/dist`. Attach `editorial.example.com` through Netlify domain management and configure DNS according to the assigned site. Do not change existing records until the target is known.

The Python API and durable worker need a separate always-on container host with persistent storage. The Compose stack currently shares SQLite and provider configuration on a local volume, so API and worker should run on the same host. Netlify is used for the static frontend, not as a Docker Compose host.

Proxy `/api/*` to the external HTTPS backend using a Netlify status-200 rewrite. This keeps browser API requests on the same origin and allows the HttpOnly session cookie. Set `MARGIN_COOKIE_SECURE=true` on the backend, use one API process and test Set-Cookie, logout, CSRF denial and cache isolation through the final proxy. Never put provider keys in frontend build variables. Long generation tasks are queued and polled, rather than holding a proxy request open.

Reference: https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/

## Single container host

A simpler first deployment is the entire Compose stack on one server with a TLS reverse proxy for the subdomain. The domain can point there even if other pages are hosted on Netlify. This avoids a second proxy layer. Back up the named volume and keep secrets out of images.

## Costs

Cost depends on the selected container host, disk/backups, Netlify usage and provider quotas. Configure Cloudflare D1 for shared persistence and GitHub Actions for scheduled discovery.
