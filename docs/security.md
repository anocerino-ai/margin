# Security policy

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/anocerino-ai/margin/security/advisories/new) for this repository. Include affected behavior, reproduction steps with dummy data, expected impact and a suggested mitigation if known. Do not include working credentials, session cookies or private content. Do not disclose an unresolved vulnerability in a public issue.

Security fixes are maintained on the main branch. Review updates before applying them and back up persistent data before schema changes.

## Deployment boundaries

Margin supports one configured administrator and no public registration. Sessions live in one API process and expire after 12 hours; API restarts invalidate them. A new successful login invalidates the previous session. Run one API process and use HTTPS with `MARGIN_COOKIE_SECURE=true` for remote deployments.

The custom mutation header supplements session authentication; it is not a credential. Keep the API behind the same-origin web proxy. Never expose the development Vite server publicly.

## Credentials and data

Provider overrides are stored in a restricted backend file as plaintext and are not returned by the API. Protect host storage and backups. Keep `.env`, credential files, databases and exports outside source control and static hosting. Host administrators and users with Docker access can read container environments and volumes.

The D1 bridge token grants SQL access to application data and must be treated as a database password. If a secret is exposed, revoke or rotate it at its provider, update every deployment that uses it, and review relevant access records. Deleting it from the latest commit alone is insufficient.

## Content and external providers

Discovery sends article titles to OpenRouter. Generation sends extracted source content and prompts to the configured providers. Enable email only for intended recipients. Review provider data policies for your deployment and avoid entering confidential material without an appropriate agreement.

Generated drafts require human review. Editorial approval does not automatically publish content to any external platform.
