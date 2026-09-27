import json
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date
from hmac import compare_digest
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

from margin.config import Settings
from margin.jobs.worker import Worker
from margin.providers.rss import RSSProvider
from margin.repositories.core import NotFound, Repository, identifier, now
from margin.runtime import open_database, require_ready, seed_models
from margin.schemas.contracts import (
    Accepted,
    ArticleView,
    EmailDelivery,
    ErrorResponse,
    FeedTest,
    Generation,
    GenerationCreate,
    GenerationDetail,
    GenerationOutput,
    GenerationSource,
    Items,
    Model,
    ModelCreate,
    ModelOrder,
    ModelUpdate,
    Page,
    Regenerate,
    Run,
    RunDetail,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    Source,
    SourceCreate,
    SourceUpdate,
    Summary,
    Topic,
    TopicCreate,
    TopicUpdate,
    Version,
)
from margin.security import load_credentials, save_credentials, verify_password
from margin.services import views
from margin.services.foundation import DiscoveryService, GenerationService


class APIError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def create_app(settings=None, database=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if database is not None:
            db = database
        else:
            db = open_database(settings)
        seed_models(db, settings)
        app.state.repo = Repository(db)
        yield
        if database is None:
            db.close()

    app = FastAPI(
        title="Margin API",
        version="0.2.0",
        lifespan=lifespan,
        description="Live API. Jobs are executed by a separate durable worker.",
    )

    def error(code, message, status):
        return JSONResponse(
            status_code=status, content={"error": {"code": code, "message": message, "details": {}}}
        )

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return error(exc.code, exc.message, exc.status)

    @app.exception_handler(NotFound)
    async def not_found(request, exc):
        return error("NOT_FOUND", "Resource not found", 404)

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflict(request, exc):
        return error(
            "CONFLICT", "Duplicate resource, invalid relation or active discovery already exists", 409
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error("VALIDATION_ERROR", "Request does not match the API contract", 422)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return error(
            "VALIDATION_ERROR",
            "Invalid request or missing provider configuration: "
            + (str(exc) if len(str(exc)) < 120 else "check fields"),
            422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error("HTTP_ERROR", str(exc.detail), exc.status_code)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, exc):
        return error(
            "CAPABILITY_UNAVAILABLE", "Storage capability unavailable; see validation checklist", 503
        )

    sessions = {}
    attempts = []

    def authorize(request: Request, authorization: str = Header(default="")):
        load_credentials(settings)
        if settings.admin_email:
            session = request.cookies.get("margin_session", "")
            if sessions.get(session, 0) < time.time():
                raise APIError("UNAUTHORIZED", "Login required", 401)
            if (
                request.method not in {"GET", "HEAD", "OPTIONS"}
                and request.headers.get("X-Requested-With") != "Margin"
            ):
                raise APIError("FORBIDDEN", "Invalid request", 403)
            return
        if settings.env != "test":
            raise APIError("ADMIN_NOT_CONFIGURED", "Configure the admin account on the server", 503)
        token = settings.api_token.get_secret_value()
        if token and not compare_digest(authorization, "Bearer " + token):
            raise APIError("UNAUTHORIZED", "Valid bearer token required", 401)

    class Login(BaseModel):
        email: str = Field(max_length=254)
        password: str = Field(max_length=1024)

    @app.post("/api/auth/login")
    def login(body: Login):
        now_ts = time.time()
        attempts[:] = [t for t in attempts if t > now_ts - 60]
        if len(attempts) >= 10:
            raise APIError("RATE_LIMIT", "Wait a minute before trying again", 429)
        attempts.append(now_ts)
        valid = verify_password(body.password, settings.admin_password_hash.get_secret_value())
        if (
            not settings.admin_email
            or not compare_digest(body.email.lower(), settings.admin_email.lower())
            or not valid
        ):
            raise APIError("UNAUTHORIZED", "Email or password incorrect", 401)
        sessions.clear()
        token = secrets.token_urlsafe(32)
        sessions[token] = now_ts + 43200
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            "margin_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=43200,
        )
        return response

    @app.get("/api/auth/session")
    def session(request: Request):
        return {
            "authenticated": sessions.get(request.cookies.get("margin_session", ""), 0) > time.time(),
            "configured": bool(settings.admin_email),
        }

    @app.post("/api/auth/logout", dependencies=[Depends(authorize)])
    def logout(request: Request):
        sessions.pop(request.cookies.get("margin_session", ""), None)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie("margin_session")
        return response

    def repo(request: Request):
        return request.app.state.repo

    router = APIRouter(
        prefix="/api/v1",
        dependencies=[Depends(authorize)],
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            501: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "milestone": "integrated-mvp"}

    def paging(
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
        search: str = Query("", max_length=200),
    ):
        return {"page": page, "page_size": page_size, "search": search}

    @router.get("/dashboard/summary", response_model=Summary)
    def summary(r=Depends(repo)):
        def count(table, where=""):
            return r.db.query(f"SELECT COUNT(*) AS n FROM {table} {where}")[0]["n"]

        return {
            "articles": count("articles"),
            "sources": count("rss_sources"),
            "active_topics": count("topics", "WHERE is_active=1"),
            "generations": count("generation_runs"),
            "drafts": count("generation_versions", "WHERE status='DRAFT'"),
        }

    @router.get("/topics", response_model=Page[Topic])
    def topics(p=Depends(paging), r=Depends(repo)):
        return r.list("topics", **p)

    @router.post("/topics", response_model=Topic, status_code=201)
    def create_topic(body: TopicCreate, r=Depends(repo)):
        return r.create_catalog("topics", body.model_dump(mode="json"))

    @router.patch("/topics/{id}", response_model=Topic)
    def update_topic(id: str, body: TopicUpdate, r=Depends(repo)):
        return r.update_catalog("topics", id, body.model_dump(mode="json", exclude_unset=True))

    @router.get("/sources", response_model=Page[Source])
    def sources(p=Depends(paging), r=Depends(repo)):
        return r.list("rss_sources", **p)

    @router.post("/sources", response_model=Source, status_code=201)
    def create_source(body: SourceCreate, r=Depends(repo)):
        return r.create_catalog("rss_sources", body.model_dump(mode="json"))

    @router.patch("/sources/{id}", response_model=Source)
    def update_source(id: str, body: SourceUpdate, r=Depends(repo)):
        current = r.get("rss_sources", id)
        values = body.model_dump(mode="json", exclude_unset=True)
        Source.model_validate({**current, **values})
        return r.update_catalog("rss_sources", id, values)

    @router.get("/articles", response_model=Page[ArticleView])
    def articles(
        p=Depends(paging),
        r=Depends(repo),
        source: str | None = None,
        classification: Literal["target", "non-target", "failed"] | None = None,
        topic: str | None = None,
        run_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        return views.articles(
            r.db,
            **p,
            source=source,
            classification=classification,
            topic=topic,
            run_id=run_id,
            date_from=date_from,
            date_to=date_to,
        )

    @router.get("/articles/{id}", response_model=ArticleView)
    def article(id: str, r=Depends(repo)):
        return views.article_view(r.db, r.get("articles", id))

    @router.get("/classification-runs", response_model=Page[Run])
    def runs(p=Depends(paging), r=Depends(repo)):
        return r.list("classification_runs", **p)

    @router.get("/classification-runs/{id}", response_model=RunDetail)
    def run(id: str, r=Depends(repo)):
        item = r.get("classification_runs", id)
        item["topics"] = r.db.query("SELECT * FROM classification_run_topics WHERE run_id=?", [id])
        item["articles"] = [
            views.article_view(r.db, a)
            for a in r.db.query(
                "SELECT a.* FROM articles a JOIN article_classifications c ON c.article_id=a.id WHERE c.run_id=?",
                [id],
            )
        ]
        for article in item["articles"]:
            c = r.db.query(
                "SELECT * FROM article_classifications WHERE article_id=? AND run_id=?", [article["id"], id]
            )[0]
            c["topics"] = r.db.query(
                "SELECT * FROM classification_topics WHERE classification_id=?", [c["id"]]
            )
            article["classification"] = c
        item["events"] = r.db.query(
            "SELECT * FROM run_events WHERE classification_run_id=? ORDER BY created_at", [id]
        )
        item["emails"] = r.db.query("SELECT * FROM email_deliveries WHERE classification_run_id=?", [id])
        return item

    @router.post("/classification-runs", response_model=Accepted, status_code=202)
    def request_discovery(r=Depends(repo)):
        require_ready(r.db, settings, "DISCOVERY")
        return DiscoveryService(r).request()

    @router.get("/generations", response_model=Page[Generation])
    def generations(p=Depends(paging), r=Depends(repo)):
        return r.list("generation_runs", **p)

    @router.post("/generations", response_model=Accepted, status_code=202)
    def create_generation(body: GenerationCreate, r=Depends(repo)):
        require_ready(r.db, settings, "GENERATION")
        return GenerationService(r).create(body)

    @router.get("/generations/{id}", response_model=GenerationDetail)
    def generation(id: str, r=Depends(repo)):
        return views.generation_detail(r, id)

    @router.get("/generations/{id}/sources", response_model=Items[GenerationSource])
    def generation_sources(id: str, r=Depends(repo)):
        r.get("generation_runs", id)
        return {"items": r.db.query("SELECT * FROM generation_sources WHERE generation_run_id=?", [id])}

    @router.get("/generations/{id}/outputs", response_model=Items[GenerationOutput])
    def generation_outputs(id: str, r=Depends(repo)):
        r.get("generation_runs", id)
        return {"items": r.db.query("SELECT * FROM generation_outputs WHERE generation_run_id=?", [id])}

    @router.get("/generation-outputs/{id}/versions/{version}", response_model=Version)
    def generation_version(id: str, version: int, r=Depends(repo)):
        rows = r.db.query(
            "SELECT * FROM generation_versions WHERE generation_output_id=? AND version=?", [id, version]
        )
        if not rows:
            raise NotFound()
        return rows[0]

    @router.post("/generation-outputs/{id}/versions/{version}/approve", response_model=Version)
    def approve(id: str, version: int, r=Depends(repo)):
        return GenerationService(r).approve(id, version)

    @router.get("/settings", response_model=RuntimeSettings)
    def get_settings(r=Depends(repo)):
        values = r.db.query("SELECT value FROM app_settings WHERE key='runtime'")
        return json.loads(values[0]["value"]) if values else RuntimeSettings()

    @router.put("/settings", response_model=RuntimeSettings)
    def put_settings(body: RuntimeSettings, r=Depends(repo)):
        r.db.batch(
            [
                (
                    "INSERT INTO app_settings VALUES ('runtime',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                    [body.model_dump_json(), now()],
                ),
                (
                    "INSERT INTO app_settings VALUES ('classification.threshold',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                    [json.dumps(body.classification_threshold), now()],
                ),
            ]
        )
        return body

    @router.patch("/settings", response_model=RuntimeSettings)
    def patch_settings(body: RuntimeSettingsUpdate, r=Depends(repo)):
        current = RuntimeSettings.model_validate(get_settings(r)).model_dump()
        changes = body.model_dump(exclude_unset=True)
        if any(value is None for value in changes.values()):
            raise ValueError("Settings cannot be null")
        if "discovery" in changes:
            changes["discovery"] = {**current["discovery"], **changes["discovery"]}
        return put_settings(RuntimeSettings.model_validate({**current, **changes}), r)

    @router.patch("/settings/llm-models/{id}", response_model=Model)
    def update_model(id: str, body: ModelUpdate, r=Depends(repo)):
        current = r.get("llm_models", id)
        updated = Model.model_validate({**current, **body.model_dump(exclude_unset=True)})
        r.db.query(
            "UPDATE llm_models SET model=?,position=?,enabled=? WHERE id=?",
            [updated.model, updated.position, updated.enabled, id],
        )
        return updated

    @router.get("/settings/llm-models", response_model=Page[Model])
    def models(p=Depends(paging), r=Depends(repo)):
        return r.list("llm_models", **p)

    @router.post("/settings/llm-models", response_model=Model, status_code=201)
    def add_model(body: ModelCreate, r=Depends(repo)):
        id = identifier()
        r.db.query("INSERT INTO llm_models VALUES (?,?,?,?)", [id, body.model, body.position, body.enabled])
        return {"id": id, **body.model_dump()}

    @router.delete("/settings/llm-models/{id}", status_code=204)
    def delete_model(id: str, r=Depends(repo)):
        r.get("llm_models", id)
        r.db.query("DELETE FROM llm_models WHERE id=?", [id])

    @router.post("/generation-outputs/{id}/versions", response_model=Accepted, status_code=202)
    def regenerate(id: str, body: Regenerate, r=Depends(repo)):
        require_ready(r.db, settings, "LLM")
        outputs = r.db.query(
            "SELECT o.*,g.status FROM generation_outputs o JOIN generation_runs g ON g.id=o.generation_run_id WHERE o.id=?",
            [id],
        )
        if not outputs:
            raise NotFound()
        if outputs[0]["status"] not in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}:
            raise APIError("GENERATION_RUNNING", "Wait for the initial generation", 409)
        if not r.db.query("SELECT id FROM generation_versions WHERE generation_output_id=?", [id]):
            raise APIError("NO_VERSION", "No previous version available", 409)
        if body.depends_on_version_id:
            valid = r.db.query(
                "SELECT v.id FROM generation_versions v JOIN generation_outputs o ON o.id=v.generation_output_id WHERE v.id=? AND o.generation_run_id=? AND o.output_type='BLOG'",
                [body.depends_on_version_id, outputs[0]["generation_run_id"]],
            )
            if outputs[0]["output_type"] != "LINKEDIN" or not valid:
                raise ValueError("INVALID_BLOG_DEPENDENCY")
        operation = identifier()
        r.db.query(
            "INSERT INTO job_outbox(id,kind,resource_id,created_at,payload) VALUES (?,'REGENERATION',?,?,?)",
            [identifier(), operation, now(), json.dumps({"output_id": id, **body.model_dump()})],
        )
        return {"id": operation, "status": "PENDING"}

    @router.post("/articles/{id}/classification/retry", response_model=Accepted, status_code=202)
    def retry_classification(id: str, r=Depends(repo)):
        r.get("articles", id)
        require_ready(r.db, settings, "LLM")
        result = DiscoveryService(r).request("RETRY", payload={"article_ids": [id]})
        return result

    @router.get("/emails", response_model=Page[EmailDelivery])
    def emails(p=Depends(paging), r=Depends(repo)):
        return r.list("email_deliveries", **p)

    @router.post("/emails/{id}/retry")
    def retry_email(id: str, r=Depends(repo)):
        row = r.get("email_deliveries", id)
        if row["status"] == "SENT":
            raise APIError("EMAIL_ALREADY_SENT", "Digest already sent", 409)
        Worker(r.db, settings).make_pipeline(r.db).send_delivery(row)
        return r.get("email_deliveries", id)

    @router.post("/sources/test")
    def test_feed(body: FeedTest):
        entries = RSSProvider().entries(str(body.feed_url), 5)
        return {"valid": True, "sample_count": len(entries), "sample_titles": [e["title"] for e in entries]}

    @router.get("/system/status")
    def system_status(r=Depends(repo)):
        worker = r.db.query(
            "SELECT heartbeat_at FROM worker_status WHERE julianday(heartbeat_at)>julianday('now','-90 seconds') ORDER BY heartbeat_at DESC LIMIT 1"
        )
        return {
            "storage": settings.storage,
            "openrouter": bool(settings.openrouter_api_key.get_secret_value()),
            "firecrawl": bool(settings.firecrawl_api_key.get_secret_value()),
            "resend": bool(
                settings.resend_api_key.get_secret_value()
                and settings.email_from
                and settings.email_recipient
            ),
            "models": len(r.db.query("SELECT id FROM llm_models WHERE enabled=1")),
            "active_sources": len(r.db.query("SELECT id FROM rss_sources WHERE is_active=1")),
            "worker_online": bool(worker),
        }

    @router.post("/settings/llm-models/reorder")
    def reorder(body: ModelOrder, r=Depends(repo)):
        rows = r.db.query("SELECT id FROM llm_models")
        if len(body.ids) != len(set(body.ids)) or set(body.ids) != {x["id"] for x in rows}:
            raise ValueError("Include every model exactly once")
        statements = [("UPDATE llm_models SET position=-position-1 WHERE position>=0", [])]
        statements += [
            ("UPDATE llm_models SET position=? WHERE id=?", [i, id]) for i, id in enumerate(body.ids)
        ]
        r.db.batch(statements)
        return {"ok": True}

    @app.exception_handler(httpx.HTTPError)
    async def provider_error(request, exc):
        return error("PROVIDER_UNAVAILABLE", "Provider request failed; check configuration and retry", 502)

    class ProviderSettings(BaseModel):
        model_config = ConfigDict(extra="forbid")
        openrouter_api_key: str = Field(default="", max_length=1024)
        firecrawl_api_key: str = Field(default="", max_length=1024)
        resend_api_key: str = Field(default="", max_length=1024)
        email_from: str = Field(default="", max_length=254)
        email_recipient: str = Field(default="", max_length=254)

    @router.get("/settings/providers")
    def provider_status():
        return {
            key: bool(
                getattr(settings, key).get_secret_value()
                if key.endswith("api_key")
                else getattr(settings, key)
            )
            for key in (
                "openrouter_api_key",
                "firecrawl_api_key",
                "resend_api_key",
                "email_from",
                "email_recipient",
            )
        }

    @router.put("/settings/providers")
    def update_providers(body: ProviderSettings):
        save_credentials(settings, body.model_dump())
        return {"saved": True}

    app.include_router(router)
    return app


app = create_app()
