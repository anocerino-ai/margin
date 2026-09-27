from fastapi.testclient import TestClient

from margin.api.app import create_app
from margin.config import ROOT, Settings
from margin.repositories.database import SQLiteDatabase
from margin.security import password_hash, verify_password


def test_admin_session_and_credentials(tmp_path):
    hashed = password_hash("a long test password")
    assert verify_password("a long test password", hashed)
    assert not verify_password("wrong", hashed)
    db = SQLiteDatabase(":memory:")
    db.migrate(ROOT / "migrations")
    settings = Settings(
        _env_file=None,
        env="test",
        admin_email="admin@example.org",
        admin_password_hash=hashed,
        credentials_path=str(tmp_path / "providers.json"),
    )
    with TestClient(create_app(settings, db)) as c:
        assert c.get("/api/v1/topics").status_code == 401
        assert (
            c.post("/api/auth/login", json={"email": "admin@example.org", "password": "wrong"}).status_code
            == 401
        )
        r = c.post("/api/auth/login", json={"email": "admin@example.org", "password": "a long test password"})
        assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
        assert c.get("/api/v1/topics").status_code == 200
        assert c.put("/api/v1/settings/providers", json={"resend_api_key": "test-secret"}).status_code == 403
        r = c.put(
            "/api/v1/settings/providers",
            headers={"X-Requested-With": "Margin"},
            json={"resend_api_key": "test-secret"},
        )
        assert r.status_code == 200 and "test-secret" not in r.text
        assert (tmp_path / "providers.json").stat().st_mode & 0o777 == 0o600
        assert "test-secret" not in c.get("/api/v1/system/status").text
        result = c.put(
            "/api/v1/settings/providers",
            headers={"X-Requested-With": "Margin"},
            json={"email_from": "Studio <sender@example.org>"},
        )
        assert result.status_code == 200
        import json

        saved = json.loads((tmp_path / "providers.json").read_text())
        assert saved["resend_api_key"] == "test-secret"
        assert saved["email_from"] == "Studio <sender@example.org>"
        presence = c.get("/api/v1/settings/providers").json()
        assert presence["resend_api_key"] is True
        assert presence["email_from"] is True
        assert presence["firecrawl_api_key"] is False
        assert "test-secret" not in str(presence)
        c.post("/api/auth/logout", headers={"X-Requested-With": "Margin"})
        assert c.get("/api/v1/topics").status_code == 401
    db.close()


def test_generation_prompts_default_to_english():
    from margin.services.prompts import load_prompt

    for kind in ("blog", "linkedin"):
        current, digest = load_prompt(kind)
        legacy, old_digest = load_prompt(kind, "v1")
        assert "English" in current and "Italian" not in current
        assert digest != old_digest
        assert "Italian" in legacy


def test_frontend_mutation_header_matches_backend():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    client = (root / "apps/web/src/data/live.ts").read_text()
    match = re.search(r'[\'"]X-Requested-With[\'"]\s*:\s*[\'"]([^\'"]+)', client)
    assert match and match.group(1) == "Margin"
