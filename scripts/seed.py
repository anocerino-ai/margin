"""Idempotent local seed; only verified RSS sources are included."""

import json

from margin.config import ROOT, Settings
from margin.repositories.core import Repository
from margin.repositories.database import SQLiteDatabase

settings = Settings()
if settings.storage != "sqlite":
    raise SystemExit("Use the D1 validation procedure for remote migrations/seeding")
db = SQLiteDatabase(settings.sqlite_path)
db.migrate(ROOT / "migrations")
repo = Repository(db)
for file, table in [("topics", "topics"), ("sources", "rss_sources")]:
    for row in json.loads((ROOT / "config" / f"{file}.json").read_text()):
        if not db.query(f"SELECT id FROM {table} WHERE name=?", [row["name"]]):
            repo.create_catalog(table, {**row, "is_active": table == "topics" or row.get("is_active", False)})
db.close()
print("Seed complete: catalogs loaded; only verified feeds enabled.")
