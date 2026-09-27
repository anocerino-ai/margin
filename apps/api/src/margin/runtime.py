import json

from margin.config import ROOT, Settings
from margin.repositories.core import identifier
from margin.repositories.database import D1Database, D1WorkerDatabase, SQLiteDatabase
from margin.schemas.contracts import RuntimeSettings


def open_database(settings: Settings):
    if settings.storage == "sqlite":
        db = SQLiteDatabase(settings.sqlite_path)
        db.migrate(ROOT / "migrations")
        return db
    if settings.storage == "d1_worker":
        return D1WorkerDatabase(settings.d1_worker_url, settings.d1_worker_token.get_secret_value())
    return D1Database(
        settings.d1_account_id, settings.d1_database_id, settings.d1_api_token.get_secret_value()
    )


def runtime_settings(db):
    rows = db.query("SELECT value FROM app_settings WHERE key='runtime'")
    return RuntimeSettings.model_validate(json.loads(rows[0]["value"]) if rows else {})


def seed_models(db, settings):
    if not db.query("SELECT id FROM llm_models LIMIT 1"):
        for position, model in enumerate(
            dict.fromkeys(x.strip() for x in settings.openrouter_models.split(",") if x.strip())
        ):
            db.query("INSERT OR IGNORE INTO llm_models VALUES (?,?,?,1)", [identifier(), model, position])


def require_ready(db, settings, kind):
    seed_models(db, settings)
    if not settings.openrouter_api_key.get_secret_value():
        raise ValueError("OPENROUTER_KEY_MISSING")
    if not db.query("SELECT id FROM llm_models WHERE enabled=1 LIMIT 1"):
        raise ValueError("NO_ENABLED_MODELS")
    if kind == "DISCOVERY" and not db.query("SELECT id FROM rss_sources WHERE is_active=1 LIMIT 1"):
        raise ValueError("NO_ACTIVE_SOURCES")
    if kind == "GENERATION" and not settings.firecrawl_api_key.get_secret_value():
        raise ValueError("FIRECRAWL_KEY_MISSING")
