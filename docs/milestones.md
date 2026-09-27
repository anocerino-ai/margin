# Component reference

Margin runs as a small set of cooperating services. The browser never calls model, extraction or database providers directly. The API accepts authenticated requests and the worker performs queued processing.

| Component | Location | Responsibility |
| --- | --- | --- |
| Vue workspace | `apps/web` | Discovery history, article library, output review, topics, sources and settings |
| FastAPI | `apps/api/src/margin/api` | Admin sessions, validation, API routes and queue submission |
| Python services | `apps/api/src/margin/services` | Classification, source preparation, generation and editorial versioning |
| Queue worker | `apps/api/src/margin/jobs` | Claim jobs, maintain leases, execute work and record failures |
| SQL adapters | `apps/api/src/margin/repositories` | Persistent records and transactions through SQLite or D1 |
| Provider adapters | `apps/api/src/margin/providers` | OpenRouter model calls, Firecrawl extraction, RSS and Resend delivery |
| Prompt library | `prompts` | Versioned Markdown instructions recorded in generation provenance |
| API contracts | `packages/contracts` | Committed OpenAPI and generated TypeScript types |
| Database migrations | `migrations`, `infra/d1-migrations` | Ordered schema evolution for local and remote databases |
| Infrastructure | `infra`, Compose files | Web proxy, container build and authenticated D1 bridge |
| GitHub workflows | `.github/workflows` | Project checks, documentation publication and scheduled discovery |
| Documentation | `docs`, `mkdocs.yml` | Searchable operator and contributor guides |

## Local execution

Docker starts initialization first, followed by API, worker and web services. Initialization applies SQLite migrations and seeds catalogs. API and worker share a persistent volume, while the web server exposes one loopback port and proxies browser API requests. The D1 override replaces initialization with a remote schema check and redirects both Python processes to the same bridge.

## Changes across boundaries

A route or schema change requires regenerated API contracts. A persistent data change requires a new migration for each supported SQL backend. A prompt behavior change requires a new version so existing outputs remain traceable. A provider change belongs behind its adapter and should be exercised with fake responses in automated tests.

## Operational ownership

GitHub Pages serves only documentation. Discovery scheduling is a separate workflow with its own enable variable and credentials. Neither workflow hosts the interactive application. The application host owns session memory and saved provider credentials; D1 owns remote application records. Back up each store according to that responsibility.
