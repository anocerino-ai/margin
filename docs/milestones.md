# Components

| Component | Responsibility |
| --- | --- |
| Vue workspace | Sources, discovery, article library, version review and settings |
| FastAPI | Admin sessions, validation and use-case orchestration |
| Queue worker | Durable job execution with ownership fencing |
| SQL adapters | SQLite or Cloudflare D1 via Worker bridge |
| Provider adapters | OpenRouter, Firecrawl and Resend |
| GitHub Actions | Scheduled discovery against shared persistence |
| MkDocs | Searchable English documentation |

See [architecture](architecture.md) for boundaries and [configuration](configuration.md) for runtime settings.
