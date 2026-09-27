"""Configure Wrangler from .env without printing secrets. Does not deploy."""

import json
import secrets

from dotenv import set_key

from margin.config import ROOT, Settings

s = Settings()
if not s.d1_database_id:
    raise SystemExit("Set MARGIN_D1_DATABASE_ID in .env first.")
path = ROOT / "infra/d1-worker/wrangler.jsonc"
config = json.loads(path.read_text())
config["d1_databases"][0]["database_id"] = s.d1_database_id
path.write_text(json.dumps(config, indent=2) + "\n")
if not s.d1_worker_token.get_secret_value():
    set_key(ROOT / ".env", "MARGIN_D1_WORKER_TOKEN", secrets.token_urlsafe(32))
print("Wrangler configured; bridge token is stored in .env. No deployment performed.")
