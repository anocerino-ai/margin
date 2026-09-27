# Installation

## Prerequisites

| Tool or account | Required when |
| --- | --- |
| Git | Cloning or contributing |
| Docker Desktop / Engine with Compose | Running the container stack |
| Python 3.12 with pip and venv | Setting up the admin locally and developing the backend |
| Node >=22.12 with npm | Local frontend development and Cloudflare tooling |
| OpenRouter | Classification and generation |
| Firecrawl | Source extraction for generation |
| Resend | Optional digest delivery |

Install [Docker](https://docs.docker.com/get-started/get-docker/), [Python](https://www.python.org/downloads/), [Node](https://nodejs.org/en/download) and [Git](https://git-scm.com/downloads) from their official distributions. Start the Docker engine before using Compose. Initial builds require network access.

## Clone and prepare

```sh
git clone https://github.com/anocerino-ai/margin.git
cd margin
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
.venv/bin/pip install --no-deps -e apps/api
.venv/bin/python scripts/admin.py
```

Copy the example only on first setup: never overwrite an existing `.env`. The admin command prompts for email and a password of at least 12 characters. See [admin login](admin.md).

Commands use macOS/Linux paths. On Windows, activate the virtual environment or use its `Scripts` equivalents.

## Start Docker

```sh
docker compose up --build -d
docker compose ps -a
```

Open <http://localhost:8080>. Expected state: `init` exited successfully, `api` healthy, and `worker` plus `web` running. Only the web port is published, bound to loopback by default. Ensure port 8080 is available.

Sign in and configure your [connections](providers.md). The fresh database includes five verified sources and initial topics; configure at least one enabled OpenRouter model before starting discovery.

## Develop without Docker

```sh
npm ci
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/dev.py
```

Open <http://127.0.0.1:5173>. The supervisor starts Vite on 5173, FastAPI on 8000 and the worker. Ctrl-C stops all three. Docker and development storage are independent; starting one does not migrate data from the other.

For the first useful run, continue with the [walkthrough](user-guide.md).
