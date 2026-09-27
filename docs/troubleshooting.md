# Troubleshooting

| Symptom | Check and next step |
| --- | --- |
| Docker cannot connect | Start Docker Desktop and wait for its engine; check `docker info`. |
| Port already in use | Stop the conflicting process or intentionally change the published web port. |
| Init exits nonzero | Read init logs; inspect migration and volume permissions before retrying. Do not delete the volume. |
| Admin not configured | Run the admin script, then recreate containers to reload `.env`. |
| Password rejected | Confirm the deployment URL and configured email; reset with the admin script if needed. |
| Login rate limited | Wait one minute. The current limiter is process-wide. |
| Logged out after restart | Expected: sessions live in API memory. Sign in again. |
| Configured key fails | Presence is not validation. Check provider account status, permissions, quotas and model support. |
| Resend rejects Gmail sender | Use the onboarding sender for tests or verify a domain you own. |
| Resend rejects recipient | Its onboarding domain only permits your account email; verify a domain for wider delivery. |
| Discovery stays pending | Confirm worker process/heartbeat and inspect worker logs. |
| Discovery returns no new articles | Known URLs are deduplicated; inspect active feeds and limits. |
| Classification fails | Check enabled models, structured-output support, quotas and attempt records. |
| Generation fails | Check extraction events and context budget; try fewer sources or a new generation. |
| Old data missing in Docker | Docker has a separate volume from local development. Verify Compose project name and volume before assuming data loss. |
| Schedule saves but never runs | Settings do not start a timer. Complete remote D1 and Actions configuration. |
| Workflow skipped | Check repository enable variable, default branch and runtime schedule. |
| Ruff differs locally and in CI | Use the exact CI command with `--config ruff.toml`; `margin` is explicitly first-party. |

Avoid sharing full environment dumps, cookies, provider files or unredacted logs. Provide the stage, status/error code and a minimal redacted reproduction instead.
