"""Read-only D1 connectivity/schema probe. Does not validate atomic writes."""

from margin.config import Settings
from margin.repositories.database import D1Database

settings = Settings(storage="d1")
db = D1Database(settings.d1_account_id, settings.d1_database_id, settings.d1_api_token.get_secret_value())
try:
    result = db.query("SELECT sqlite_version() AS version, ? AS parameter", ["margin-probe"])
    assert result[0]["parameter"] == "margin-probe"
    tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row["name"] for row in tables}
    required = {"articles", "generation_versions", "classification_runs", "job_outbox"}
    print("Connectivity and parameter binding: OK")
    print(
        "Foundation tables:",
        "OK" if required <= names else "MISSING — apply migrations to a test D1 database first",
    )
    print("Atomic writes: NOT VALIDATED; multi-statement operations remain gated.")
finally:
    db.close()
