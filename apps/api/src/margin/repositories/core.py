from datetime import UTC, datetime
from math import ceil
from uuid import uuid4

from margin.repositories.database import Database

TABLES = {
    "topics",
    "rss_sources",
    "articles",
    "classification_runs",
    "generation_runs",
    "email_deliveries",
    "llm_models",
}


def now():
    return datetime.now(UTC).isoformat()


def identifier():
    return uuid4().hex


class NotFound(Exception):
    pass


class Repository:
    def __init__(self, db: Database):
        self.db = db

    def list(self, table, page=1, page_size=25, search=""):
        if table not in TABLES:
            raise ValueError("Unknown resource")
        field = "title" if table == "articles" else "name" if table in {"topics", "rss_sources"} else "id"
        condition = f" WHERE {field} LIKE ?"
        params = ["%" + search + "%"]
        total = self.db.query(f"SELECT COUNT(*) AS n FROM {table}" + condition, params)[0]["n"]
        rows = self.db.query(
            f"SELECT * FROM {table}" + condition + " ORDER BY rowid DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        )
        return {
            "items": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": ceil(total / page_size),
            },
        }

    def get(self, table, id):
        if table not in TABLES:
            raise ValueError("Unknown resource")
        rows = self.db.query(f"SELECT * FROM {table} WHERE id=?", [id])
        if not rows:
            raise NotFound(table)
        return rows[0]

    def create_catalog(self, table, values):
        if table not in {"topics", "rss_sources"}:
            raise ValueError("Not a catalog")
        record = {"id": identifier(), **values, "created_at": now(), "updated_at": now()}
        columns = list(record)
        self.db.query(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            list(record.values()),
        )
        return record

    def update_catalog(self, table, id, values):
        current = self.get(table, id)
        if table not in {"topics", "rss_sources"}:
            raise ValueError("Not a catalog")
        # Preserve non-nullable columns; explicit feed_url=null is allowed.
        if any(v is None and k != "feed_url" for k, v in values.items()):
            raise ValueError("Field cannot be null")
        values["updated_at"] = now()
        self.db.query(
            f"UPDATE {table} SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
            [*values.values(), id],
        )
        return {**current, **values}
