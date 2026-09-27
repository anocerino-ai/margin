"""SQL port. Atomic batches are explicit; no remote transaction emulation."""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

import httpx

Statement = tuple[str, list[Any]]


class Database(Protocol):
    def query(self, sql: str, params: list[Any] = ...) -> list[dict]: ...
    def batch(self, statements: list[Statement]) -> list[list[dict]]: ...
    def close(self) -> None: ...


class SQLiteDatabase:
    def __init__(self, path: str):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.lock = threading.RLock()

    def query(self, sql, params=None):
        return self.batch([(sql, params or [])])[0]

    def batch(self, statements):
        with self.lock, self.connection:
            return [
                [dict(row) for row in self.connection.execute(sql, params).fetchall()]
                for sql, params in statements
            ]

    def migrate(self, directory: Path):
        self.query(
            "CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, sha256 TEXT NOT NULL)"
        )
        import hashlib

        for file in sorted(directory.glob("*.sql")):
            script = file.read_text()
            digest = hashlib.sha256(script.encode()).hexdigest()
            applied = self.query("SELECT sha256 FROM schema_migrations WHERE name=?", [file.name])
            if applied:
                if applied[0]["sha256"] != digest:
                    raise RuntimeError("Applied migration was modified: " + file.name)
                continue
            # executescript needs explicit BEGIN to make DDL and ledger atomic.
            try:
                self.connection.executescript("BEGIN;\n" + script)
                self.connection.execute("INSERT INTO schema_migrations VALUES (?,?)", [file.name, digest])
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def close(self):
        self.connection.close()


class D1Database:
    """Read/single-statement REST adapter. Multi-write is gated pending remote validation.

    Use a Worker DB.batch bridge if REST atomic rollback is not guaranteed by the
    deployment validation. Never silently execute a transaction as individual HTTP calls.
    """

    def __init__(self, account_id: str, database_id: str, token: str, client=None):
        self.url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
        )
        self.client = client or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {token}"}

    def query(self, sql, params=None):
        response = self.client.post(self.url, headers=self.headers, json={"sql": sql, "params": params or []})
        response.raise_for_status()
        payload = response.json()
        if (
            not payload.get("success")
            or not payload.get("result")
            or not all(x.get("success") for x in payload["result"])
        ):
            raise RuntimeError("D1_QUERY_FAILED")
        return payload["result"][0].get("results", [])

    def batch(self, statements):
        if len(statements) != 1:
            raise RuntimeError("D1_ATOMIC_BATCH_NOT_VALIDATED")
        return [self.query(*statements[0])]

    def close(self):
        self.client.close()


class D1WorkerDatabase:
    """Authenticated bridge to Cloudflare's transactional DB.batch binding."""

    def __init__(self, url, token, client=None):
        self.url = url.rstrip("/") + "/batch"
        self.token = token
        self.client = client or httpx.Client(timeout=45)

    def query(self, sql, params=None):
        return self.batch([(sql, params or [])])[0]

    def batch(self, statements):
        response = self.client.post(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "statements": [
                    {"sql": sql, "params": [int(p) if isinstance(p, bool) else p for p in params]}
                    for sql, params in statements
                ]
            },
        )
        if response.status_code == 409:
            raise sqlite3.IntegrityError("D1_CONSTRAINT")
        response.raise_for_status()
        data = response.json()
        if not data.get("success") or len(data.get("results", [])) != len(statements):
            raise RuntimeError("D1_BATCH_FAILED")
        return [row.get("results", []) for row in data["results"]]

    def close(self):
        self.client.close()
