# Setup

Create `.env` from `.env.example` without overwriting existing credentials. Run `scripts/admin.py` with the project virtual environment to configure the sole administrator. Restart the API after admin changes.

Start locally with `.venv/bin/python scripts/dev.py`, or use `docker compose up --build -d`. Add provider credentials individually in Settings. They are stored in the backend credential file with restrictive permissions, and shared with the worker. They override `.env` values for subsequent jobs.

For Resend testing, use `Margin <onboarding@resend.dev>` as sender and your Resend account email as recipient. Verify your own domain before sending to other recipients.

## Remote setup

Create a private or public GitHub repository without initial files, then connect the existing project. Create a Cloudflare account and D1 database only when ready to validate remote persistence. Put its database ID in `MARGIN_D1_DATABASE_ID`, then run `scripts/setup_remote.py`. This prepares configuration without deploying.

The discovery workflow stays gated by `MARGIN_SCHEDULE_ENABLED`. Do not enable it until the remote bridge, migrations, catalog and model configuration have been validated. Provider overrides currently use a local file and are not synchronized to GitHub Actions; scheduled jobs need their own GitHub secrets. The workflow does not host the dashboard or API.
