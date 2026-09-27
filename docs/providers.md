# Provider connections

Open **Settings → Connections** after signing in. Each connection is independent: editing one must not replace any other value.

## Field behavior

A configured field shows a fixed set of masking dots and **Edit**. Those dots reveal neither the stored secret nor its length. Clicking Edit starts an empty field with Save and Cancel. An unconfigured field is immediately writable.

Saved credentials are never returned to the browser. Only boolean presence indicators are returned. The browser necessarily holds a newly typed value while submitting it, then clears it after a successful save. “Configured” means a nonempty value is stored, not that the external service has accepted it.

Blank submissions preserve the existing value. There is currently no UI action to delete a saved connection. Overrides are stored in a private backend file and apply to subsequent jobs; already-running calls may use their original configuration.

## OpenRouter

Create a key at [OpenRouter API Keys](https://openrouter.ai/keys). Save it in its connection field. In the model section, add an exact model ID supporting structured output, enable it and set the desired order. Consult the [model catalog](https://openrouter.ai/models) for current availability and costs; free models can change or be rate-limited.

Margin rotates the starting model and falls back through enabled models when requests or structured output validation fail. Attempts are recorded. A configured key alone is insufficient without an enabled model.

## Firecrawl

Get a key from the [Firecrawl dashboard](https://www.firecrawl.dev/app) and save it separately. See the [API introduction](https://docs.firecrawl.dev/introduction). Firecrawl retrieves full source text only for content generation. Discovery does not spend Firecrawl credits.

Cached snapshots can be reused. Selecting refresh requests new extraction. A successful key configuration does not guarantee every publisher permits extraction.

## Resend and email addresses

Create a **Sending access** key at [Resend](https://resend.com/api-keys). See [key permissions](https://resend.com/docs/dashboard/api-keys/introduction). Save it, then save Sender email and Recipient email separately.

For a first test, set the sender to `Margin <onboarding@resend.dev>` and the recipient to your Resend signup email. For other recipients, [verify a domain you control](https://resend.com/docs/dashboard/domains/introduction), then use a sender on that domain. Gmail is a recipient address, not a domain you can verify as your Resend sender.

Enable **Send a digest after discovery** and save runtime settings when ready. A digest may report zero target articles. An API success means the provider accepted the email, not that the recipient has opened or received it in their inbox.

## Storage and rotation

Overrides live at `MARGIN_CREDENTIALS_PATH`; in Docker this is `/app/data/providers.json` on the persistent volume. The file has restrictive permissions but is not encrypted by the application. Protect host disks and backups. It is excluded from Git and images.

Environment values remain fallback configuration. UI changes do not synchronize to GitHub Actions. Rotate a key in the provider dashboard, save the replacement locally, and update any scheduled-run secrets separately.

## Discovery selection and diagnostics

Discovery selects new articles in rounds across active sources, preserving feed order within each source. With five sources that each have enough new entries, a limit of 20 selects four per source. Empty, failed or exhausted feeds release their slots to the remaining sources. Known URLs and duplicates do not consume the new-article budget. The per-feed fetch limit still bounds the candidates available for selection; a run may finish below its overall limit.

Open an article and expand **Classification attempts** to inspect model, attempt number, status and error code. New attempts distinguish HTTP status codes (such as `PROVIDER_HTTP_429`), network failures, timeouts, truncated or empty output, invalid response structure, schema error categories and topic mismatches. Provider response bodies, credentials and source content are not included in diagnostics. Older attempts retain their original generic codes.

The provider makes up to two sequential attempts per enabled model, rotating the starting model and falling back only after its attempt budget is exhausted. The default wait is 45 seconds before the second attempt; after the second failure, a 90-second cooldown precedes another model. A longer provider Retry-After is respected. Success stops further attempts; three failing models produce six recorded calls. A persisted 429 cooldown also delays subsequent operations sharing the database. The worker renews its lease during waits. These waits reduce request pressure but cannot override daily quotas or guarantee success. New diagnostics also appear in worker logs. After updating the application, rebuild the containers and refresh the browser to use the matching frontend and backend.
