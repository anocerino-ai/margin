import json
import sqlite3
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from margin.api.app import create_app
from margin.config import ROOT, Settings
from margin.jobs.discovery import due_slot
from margin.providers.openrouter import ModelsExhausted, OpenRouterProvider
from margin.repositories.core import Repository, now
from margin.repositories.database import D1Database, SQLiteDatabase
from margin.schemas.contracts import ClassificationResult, GenerationCreate
from margin.services.foundation import DiscoveryService, GenerationService


@pytest.fixture
def db():
    database = SQLiteDatabase(":memory:")
    database.migrate(ROOT / "migrations")
    yield database
    database.close()


@pytest.fixture
def repo(db):
    repository = Repository(db)
    source = repository.create_catalog(
        "rss_sources",
        dict(
            name="Test",
            feed_url="https://example.org/feed",
            website_url="https://example.org",
            is_active=True,
        ),
    )
    stamp = now()
    db.query(
        "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            "a1",
            source["id"],
            "Title",
            "https://example.org/article",
            "https://example.org/article",
            None,
            None,
            stamp,
            stamp,
            stamp,
        ],
    )
    return repository


def test_migrations_idempotent_and_foreign_keys(db):
    db.migrate(ROOT / "migrations")
    assert db.query("SELECT COUNT(*) n FROM schema_migrations")[0]["n"] == 3
    with pytest.raises(sqlite3.IntegrityError):
        db.query("INSERT INTO generation_outputs VALUES (?,?,?,?)", ["o", "missing", "BLOG", now()])


def test_generation_selection_atomic(repo):
    service = GenerationService(repo)
    result = service.create(GenerationCreate(article_ids=["a1"], outputs=["BLOG", "LINKEDIN"]))
    assert result["status"] == "PENDING"
    assert len(repo.db.query("SELECT * FROM generation_sources")) == 1
    assert len(repo.db.query("SELECT * FROM generation_outputs")) == 2
    assert repo.db.query("SELECT * FROM job_outbox")[0]["resource_id"] == result["id"]
    assert repo.db.query("SELECT * FROM generation_sources")[0]["article_title"] == "Title"


def test_failed_enqueue_rolls_back(repo):
    class BrokenDispatcher:
        def enqueue_statement(self, *args):
            return ("INSERT INTO missing_table VALUES (?)", ["bad"])

    with pytest.raises(sqlite3.OperationalError):
        GenerationService(repo, BrokenDispatcher()).create(
            GenerationCreate(article_ids=["a1"], outputs=["BLOG"])
        )
    assert repo.db.query("SELECT * FROM generation_runs") == []
    assert repo.db.query("SELECT * FROM generation_sources") == []


def test_approval_and_immutable_content(repo):
    service = GenerationService(repo)
    service.create(GenerationCreate(article_ids=["a1"], outputs=["BLOG"]))
    output = repo.db.query("SELECT id FROM generation_outputs")[0]["id"]
    for number in [1, 2]:
        repo.db.query(
            "INSERT INTO generation_versions(id,generation_output_id,version,title,content_markdown,additional_instructions,model_used,prompt_version,prompt_hash,status,created_at,approved_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                f"v{number}",
                output,
                number,
                "Title",
                f"Body {number}",
                "",
                "model",
                "v1",
                "hash",
                "DRAFT",
                now(),
                None,
            ],
        )
    service.approve(output, 1)
    service.approve(output, 2)
    assert [
        r["status"] for r in repo.db.query("SELECT status FROM generation_versions ORDER BY version")
    ] == ["ARCHIVED", "APPROVED"]
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.query("UPDATE generation_versions SET content_markdown='changed' WHERE id='v1'")
    assert (
        repo.db.query("SELECT content_markdown FROM generation_versions WHERE id='v1'")[0]["content_markdown"]
        == "Body 1"
    )


def test_discovery_snapshot_and_lock(repo):
    topic = repo.create_catalog("topics", dict(name="LLM", description="Before", is_active=True))
    DiscoveryService(repo).request()
    repo.update_catalog("topics", topic["id"], {"name": "Renamed"})
    assert repo.db.query("SELECT topic_name FROM classification_run_topics")[0]["topic_name"] == "LLM"
    with pytest.raises(sqlite3.IntegrityError):
        DiscoveryService(repo).request()
    assert len(repo.db.query("SELECT * FROM job_outbox")) == 1


def test_contract_validation():
    for payload in [
        dict(article_ids=[], outputs=["BLOG"]),
        dict(article_ids=["a"], outputs=[]),
        dict(article_ids=["a", "a"], outputs=["BLOG"]),
        dict(article_ids=["a"], outputs=["VIDEO"]),
    ]:
        with pytest.raises(ValidationError):
            GenerationCreate(**payload)
    with pytest.raises(ValidationError):
        ClassificationResult(target_topics=[{"topic": "LLM", "confidence": 1.1}], non_target_topics=[])


def test_api_errors_auth_and_pagination(db):
    with TestClient(create_app(Settings(_env_file=None, env="test", api_token="secret"), db)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/topics").status_code == 401
        headers = {"Authorization": "Bearer secret"}
        bad = client.get("/api/v1/topics?page_size=101", headers=headers)
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
        response = client.post("/api/v1/topics", json={"name": "LLM"}, headers=headers)
        assert response.status_code == 201
        assert client.post("/api/v1/topics", json={"name": "llm"}, headers=headers).status_code == 409
        assert client.get("/api/v1/articles/nope", headers=headers).status_code == 404
        assert client.get("/api/v1/topics", headers=headers).json()["pagination"]["total"] == 1
        assert "api_token" not in client.get("/api/v1/settings", headers=headers).text
        assert (
            client.post("/api/v1/generation-outputs/x/versions", json={}, headers=headers).status_code == 422
        )


def test_provider_fallback_and_rotation(db):
    db.query("INSERT INTO llm_models VALUES ('a','model-a',0,1)")
    db.query("INSERT INTO llm_models VALUES ('b','model-b',1,1)")
    calls = []

    def handler(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "model-a":
            return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"target_topics":[],"non_target_topics":[]}'}}]}
        )

    provider = OpenRouterProvider(db, "fake", httpx.Client(transport=httpx.MockTransport(handler)))
    for id in ["op1", "op2"]:
        provider.generate("prompt", "Title", ClassificationResult, id, "CLASSIFICATION")
    assert calls == ["model-a", "model-b", "model-b"]
    assert [x["status"] for x in db.query("SELECT status FROM llm_attempts")] == [
        "INVALID_OUTPUT",
        "SUCCESS",
        "SUCCESS",
    ]


def test_provider_exhaustion_is_not_non_target(db):
    db.query("INSERT INTO llm_models VALUES ('a','model-a',0,1)")
    provider = OpenRouterProvider(
        db, "fake", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    )
    with pytest.raises(ModelsExhausted):
        provider.generate("p", "c", ClassificationResult, "op", "CLASSIFICATION")
    assert db.query("SELECT status FROM llm_attempts")[0]["status"] == "HTTP_ERROR"


def test_d1_contract_and_atomic_gate():
    def handler(request):
        assert json.loads(request.content) == {"sql": "SELECT ? AS n", "params": [1]}
        return httpx.Response(
            200, json={"success": True, "result": [{"success": True, "results": [{"n": 1}]}]}
        )

    db = D1Database("account", "database", "fake", httpx.Client(transport=httpx.MockTransport(handler)))
    assert db.query("SELECT ? AS n", [1]) == [{"n": 1}]
    with pytest.raises(RuntimeError, match="NOT_VALIDATED"):
        db.batch([("a", []), ("b", [])])


def test_scheduler_timezone_and_dst():
    assert due_slot(datetime(2026, 9, 28, 7, tzinfo=UTC)) == "2026-09-28T06:00:00+00:00"
    assert due_slot(datetime(2026, 10, 26, 8, tzinfo=UTC)) == "2026-10-26T07:00:00+00:00"


def test_production_requires_auth():
    with pytest.raises(ValidationError):
        Settings(env="production", api_token="")
