# Margin

Margin is a self-hosted workspace for discovering engineering articles and turning selected sources into reviewed English blog and LinkedIn drafts. It combines a Vue interface, Python/FastAPI services, a durable SQL queue and configurable AI providers.

## Choose your path

- **Run the application:** follow [installation](installation.md), configure [admin login](admin.md), then add [provider connections](providers.md).
- **Create content:** follow the [first discovery and draft walkthrough](user-guide.md).
- **Operate your workspace:** learn about [Docker, persistence and backups](operations.md) and [troubleshooting](troubleshooting.md).
- **Host it remotely:** review [deployment options](deployment.md), then [D1](cloudflare.md) and [scheduled discovery](github-actions.md).
- **Contribute:** start with [architecture](architecture.md) and the [developer workflow](development.md).

## What is available

The local Docker stack is validated: frontend, API, worker, initialization and persistent SQLite storage. Authentication supports one configured administrator and no registration. Individual connection settings never return saved keys to the browser.

Discovery uses RSS titles, while Firecrawl runs only during content generation. Generated versions preserve source snapshots and prompt provenance. Outputs require human review; Margin does not automatically publish them.

## Runtime model

Use SQLite for a local workspace or the authenticated Cloudflare D1 bridge for shared persistence. GitHub Actions wakes scheduled discovery jobs against D1; the queue worker executes jobs. Docker and local development can point to separate databases. Session storage supports one API process; restarting it signs users out.

See [verification](verification.md) for reproducible checks and [operations](operations.md) for persistence and deployment commands.
