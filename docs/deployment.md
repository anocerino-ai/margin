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

## Free hosting options and application requirements

Margin requires two Python processes: the HTTP API and a durable job worker. Hosting the HTTP process alone does not execute queued jobs. It also stores admin sessions in memory and UI-edited provider credentials in a local file, so sleeping instances and ephemeral filesystems affect login continuity and saved configuration. D1 protects database records, but it does not persist that local credentials file.

| Option | Free-tier behavior | Fit for Margin |
| --- | --- | --- |
| Oracle Cloud Always Free VM | Eligible compute resources within account quotas; availability varies and idle instances may be reclaimed | Closest fit for the existing Docker stack; requires server administration, persistent disk backups, firewall and TLS setup |
| Render Free web service | Sleeps after 15 minutes without inbound traffic; filesystem is ephemeral | Useful for API demonstrations, not a reliable always-running job worker; provider overrides need a persistent design |
| Koyeb Free web instance | Scales to zero after one hour without traffic | Suitable for constrained API demos; background execution and durable secrets require adaptation |

For the existing code, an eligible Oracle VM can run API and worker on one host with the D1 profile, while Netlify serves the frontend. Free capacity is not guaranteed, and only resources marked eligible and kept within quota remain free. Do not provision paid shapes or extras assuming the entire account is free.

A sleeping API combined with GitHub Actions can reduce always-on requirements, but queued manual generation will not necessarily run immediately. That is a different execution design, not a drop-in equivalent of the current application. Model and extraction provider usage remains separately billed or quota-limited regardless of hosting.

Sources: [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Render Free services](https://render.com/docs/free), [Koyeb scale-to-zero](https://www.koyeb.com/docs/run-and-scale/scale-to-zero).

## Netlify setup values

Use the repository root as the build base, `npm run build` as the build command after dependency installation, and `apps/web/dist` as the publish directory. Add the desired subdomain in Netlify domain management and apply the DNS target provided by Netlify.

Add a status-200 proxy rewrite from `/api/*` to your backend's HTTPS `/api/:splat` path before any catch-all rewrite. Keep provider credentials only on the backend. Validate the login cookie through the final domain, set secure cookies on the backend, and ensure authenticated responses are not cached by shared proxies.

The Python process must bind to the host/port expected by its hosting platform. Run a worker separately or supervise both processes explicitly. The repository Compose file publishes only to loopback: place a TLS reverse proxy in front of it when exposing a VM to the internet. Do not expose the development Vite server publicly.
