# Scheduled discovery with GitHub Actions

Prerequisites: repository on GitHub, validated D1 bridge, migrations applied, remote sources/topics/models seeded, and schedule configured in the remote workspace. Local Docker SQLite cannot be shared with a GitHub-hosted runner.

## Repository secrets and variables

Open **Settings → Secrets and variables → Actions** on your repository.

| Name | Type | Value |
| --- | --- | --- |
| `MARGIN_D1_WORKER_TOKEN` | Secret | Same token as the Worker's BRIDGE_TOKEN |
| `MARGIN_OPENROUTER_API_KEY` | Secret | Classification/generation key |
| `MARGIN_FIRECRAWL_API_KEY` | Secret | Generation key; worker may process pending generation jobs |
| `MARGIN_RESEND_API_KEY` | Secret | Sending key, if digest is enabled |
| `MARGIN_EMAIL_RECIPIENT` | Secret | Digest recipient |
| `MARGIN_D1_WORKER_URL` | Variable | Deployed HTTPS bridge base URL |
| `MARGIN_EMAIL_FROM` | Variable | Verified sender or permitted test sender |
| `MARGIN_SCHEDULE_ENABLED` | Variable | Keep `false` until ready; then set `true` |

Do not add your admin password or browser session cookie: the workflow accesses the database through the bridge, not the HTTP dashboard login. UI provider edits remain local to their deployment; update GitHub secrets separately when rotating keys.

## First run

1. Ensure `.github/workflows/discovery.yml` exists on the default branch.
2. Enable the desired runtime schedule on the remote database.
3. Set `MARGIN_SCHEDULE_ENABLED=true`.
4. Open **Actions → Discovery heartbeat → Run workflow**.
5. Inspect the job result and the resulting run in the dashboard connected to D1. A manual workflow dispatch still checks whether discovery is due; use the dashboard's **Run discovery now** for an unconditional manual discovery.

The workflow wakes hourly at minute 17 (UTC cron); application settings decide which daily/weekly slot is due in your configured timezone. Duplicate slots are prevented. GitHub scheduling can be delayed and is not an exact-time guarantee. Public repositories can have scheduled workflows disabled after inactivity. Set the enable variable back to `false` to stop future scheduler jobs.

The runner drains eligible queued jobs as well as discovery. Keep its provider configuration consistent with the dashboard deployment. This workflow does not host the UI or keep an API server running.

References: [Workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow), [Using secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions).
