"""Validate remote bridge authentication, constraints and atomic rollback using temporary probe data."""

import sqlite3
from uuid import uuid4

import httpx

from margin.config import Settings
from margin.repositories.database import D1WorkerDatabase

s = Settings()
db = D1WorkerDatabase(s.d1_worker_url, s.d1_worker_token.get_secret_value())
name = "probe_" + uuid4().hex
try:
    assert httpx.post(s.d1_worker_url.rstrip("/") + "/batch", json={"statements": []}).status_code == 401
    assert db.query("SELECT ? AS value", ["bound"])[0]["value"] == "bound"
    db.query(f"CREATE TABLE {name}(id TEXT PRIMARY KEY, value INTEGER CHECK(value>0))")
    try:
        db.batch(
            [
                (f"INSERT INTO {name} VALUES (?,?)", ["duplicate", 1]),
                (f"INSERT INTO {name} VALUES (?,?)", ["duplicate", 2]),
            ]
        )
        raise AssertionError("Duplicate batch was accepted")
    except sqlite3.IntegrityError:
        assert db.query(f"SELECT COUNT(*) AS n FROM {name}")[0]["n"] == 0
    try:
        db.query("INSERT INTO worker_guards VALUES (?,?)", [name, "invalid-owner"])
        raise AssertionError("Invalid lease was accepted")
    except sqlite3.IntegrityError:
        pass
    required = {"articles", "generation_versions", "classification_runs", "job_outbox", "worker_guards"}
    assert required <= {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    print(
        "PASS: unauthorized access rejected, parameter binding, schema, atomic rollback and invalid lease rejection"
    )
finally:
    db.query(f"DROP TABLE IF EXISTS {name}")
    db.close()
