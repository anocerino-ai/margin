import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from margin.config import ROOT, Settings
from margin.jobs.worker import FencedDatabase, Worker
from margin.providers.rss import FetchError, RSSProvider, normalize_url, public_addresses
from margin.repositories.core import Repository
from margin.repositories.database import SQLiteDatabase
from margin.schemas.contracts import ClassificationResult, ContentResult, GenerationCreate
from margin.services.foundation import DiscoveryService, GenerationService
from margin.services.pipelines import PipelineFailure, Pipelines


@pytest.fixture
def setup():
    db = SQLiteDatabase(":memory:")
    db.migrate(ROOT / "migrations")
    repo = Repository(db)
    repo.create_catalog("topics", {"name": "LLM", "description": "Models", "is_active": True})
    source = repo.create_catalog(
        "rss_sources",
        {
            "name": "Source",
            "feed_url": "https://example.org/feed",
            "website_url": "https://example.org",
            "is_active": True,
        },
    )
    settings = Settings(
        _env_file=None,
        env="test",
        api_token="",
        openrouter_api_key="fake",
        firecrawl_api_key="fake",
        resend_api_key="fake",
        email_from="from@example.org",
        email_recipient="to@example.org",
    )
    yield db, repo, settings, source
    db.close()


class FakeRSS:
    def entries(self, url, limit):
        return [
            {
                "title": "LLM architecture",
                "url": "https://example.org/a",
                "rss_guid": "a",
                "published_at": None,
            }
        ]


class FakeLLM:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, context, schema, operation_id, operation_type, validate=None):
        self.calls.append((operation_type, json.loads(context)))
        result = (
            ClassificationResult(target_topics=[{"topic": "LLM", "confidence": 0.95}], non_target_topics=[])
            if schema == ClassificationResult
            else ContentResult(title="A draft", content_markdown="Grounded draft from sources.")
        )
        if validate:
            validate(result)
        return result


class FakeCrawl:
    def __init__(self):
        self.calls = []

    def crawl(self, url, force_refresh=False):
        self.calls.append(url)
        return "Engineering evidence."


class FakeEmail:
    def __init__(self):
        self.calls = []

    def send(self, *args):
        self.calls.append(args)
        return "email-1"


def pipeline(db, settings, llm=None, crawl=None, email=None):
    return Pipelines(db, settings, llm or FakeLLM(), FakeRSS(), crawl or FakeCrawl(), email or FakeEmail())


def discover(db, repo, settings):
    result = DiscoveryService(repo).request()
    pipeline(db, settings).discovery(result["id"])
    return result["id"]


def test_discovery_idempotent_titles_only(setup):
    db, repo, settings, _ = setup
    llm = FakeLLM()
    crawl = FakeCrawl()
    p = pipeline(db, settings, llm, crawl)
    run = DiscoveryService(repo).request()
    p.discovery(run["id"])
    assert repo.get("classification_runs", run["id"])["target_count"] == 1
    assert "markdown" not in llm.calls[0][1]
    assert not crawl.calls
    second = DiscoveryService(repo).request()
    p.discovery(second["id"])
    assert len(db.query("SELECT * FROM articles")) == 1
    assert len(llm.calls) == 1
    assert repo.get("classification_runs", second["id"])["known_articles"] == 1


def test_worker_executes_and_fences(setup):
    db, repo, settings, _ = setup
    run = DiscoveryService(repo).request()
    worker = Worker(db, settings, lambda fenced: pipeline(fenced, settings))
    assert worker.once()
    assert db.query("SELECT status FROM job_outbox")[0]["status"] == "COMPLETED"
    assert repo.get("classification_runs", run["id"])["status"] == "COMPLETED"
    assert db.query("SELECT * FROM worker_guards") == []
    assert not worker.once()
    with pytest.raises(sqlite3.IntegrityError):
        FencedDatabase(db, db.query("SELECT id FROM job_outbox")[0]["id"], "stale").query("SELECT 1")


def test_worker_recovers_expired_owner(setup):
    db, repo, settings, _ = setup
    DiscoveryService(repo).request()
    first = Worker(db, settings)
    claimed = first.claim()[0]
    db.query(
        "UPDATE job_outbox SET lease_until=? WHERE id=?",
        [(datetime.now(UTC) - timedelta(minutes=1)).isoformat(), claimed["id"]],
    )
    second = Worker(db, settings, lambda fenced: pipeline(fenced, settings))
    new = second.claim()[0]
    assert new["owner"] != claimed["owner"] and new["attempts"] == 2
    with pytest.raises(sqlite3.IntegrityError):
        FencedDatabase(db, claimed["id"], first.owner).query("SELECT 1")


def test_generation_dependency_cache_and_regeneration(setup):
    db, repo, settings, _ = setup
    discover(db, repo, settings)
    article = db.query("SELECT id FROM articles")[0]["id"]
    run = GenerationService(repo).create(
        GenerationCreate(article_ids=[article], outputs=["BLOG", "LINKEDIN"])
    )
    llm = FakeLLM()
    crawl = FakeCrawl()
    p = pipeline(db, settings, llm, crawl)
    p.generation(run["id"])
    assert repo.get("generation_runs", run["id"])["status"] == "COMPLETED"
    assert len(db.query("SELECT * FROM generation_versions")) == 2
    dependency = db.query("SELECT * FROM generation_version_dependencies")[0]
    assert llm.calls[1][1]["blog"] == "Grounded draft from sources."
    blog = db.query("SELECT * FROM generation_outputs WHERE output_type='BLOG'")[0]
    p.regenerate(blog["id"], {"additional_instructions": "More detail"}, "regen1")
    assert len(db.query("SELECT * FROM generation_versions")) == 3
    assert db.query("SELECT * FROM generation_version_dependencies")[0] == dependency
    p.regenerate(blog["id"], {"additional_instructions": "More detail"}, "regen1")
    assert len(db.query("SELECT * FROM generation_versions")) == 3
    second = GenerationService(repo).create(GenerationCreate(article_ids=[article], outputs=["LINKEDIN"]))
    p.generation(second["id"])
    assert len(crawl.calls) == 1
    assert llm.calls[-1][1]["blog"] is None


def test_no_sources_and_context_budget_fail_visibly(setup):
    db, repo, settings, _ = setup
    discover(db, repo, settings)
    article = db.query("SELECT id FROM articles")[0]["id"]
    run = GenerationService(repo).create(GenerationCreate(article_ids=[article], outputs=["BLOG"]))

    class BadCrawl:
        def crawl(self, *args, **kwargs):
            raise ValueError("failed")

    with pytest.raises(PipelineFailure, match="NO_VALID_SOURCES"):
        pipeline(db, settings, crawl=BadCrawl()).generation(run["id"])
    assert db.query("SELECT crawl_status FROM generation_sources")[0]["crawl_status"] == "FAILED"
    assert not db.query("SELECT * FROM generation_versions")


def test_digest_zero_targets_and_idempotency(setup):
    db, repo, settings, _ = setup
    id = discover(db, repo, settings)
    email = FakeEmail()
    p = pipeline(db, settings, email=email)
    p.digest(id)
    p.digest(id)
    assert len(email.calls) == 1
    assert db.query("SELECT status FROM email_deliveries")[0]["status"] == "SENT"
    next_run = DiscoveryService(repo).request()
    p.discovery(next_run["id"])
    p.digest(next_run["id"])
    assert "No target articles" in email.calls[-1][2]


def test_rss_parse_and_normalization():
    feed = b'<rss version="2.0"><channel><title>Test</title><item><title>Hello</title><link>https://example.org/a?utm_source=test&amp;x=1#fragment</link></item></channel></rss>'
    assert (
        RSSProvider(lambda url: feed).entries("https://example.org")[0]["url"] == "https://example.org/a?x=1"
    )
    assert normalize_url("https://EXAMPLE.org:443/a?utm_source=x&amp=1#x") == "https://example.org/a?amp=1"
    with pytest.raises(FetchError):
        normalize_url("file:///etc/passwd")
    with pytest.raises(FetchError):
        public_addresses("http://127.0.0.1")
    with pytest.raises(FetchError):
        RSSProvider(lambda url: b"<!DOCTYPE x><rss/>").entries("https://example.org")


@pytest.mark.parametrize(
    "sizes,expected",
    [
        ([20, 20, 20, 20, 20], [4, 4, 4, 4, 4]),
        ([1, 20, 20, 20, 20], [1, 5, 5, 5, 4]),
        ([0, 0, 2, 3, 1], [0, 0, 2, 3, 1]),
    ],
)
def test_balanced_selection(sizes, expected):
    from collections import Counter

    from margin.services.selection import balanced_entries

    counts = Counter(
        source for source, _ in balanced_entries([(i, list(range(n))) for i, n in enumerate(sizes)], 20)
    )
    assert [counts[i] for i in range(5)] == expected


def test_discovery_balances_sources_and_resumes(setup):
    db, repo, settings, original = setup
    sources = [original]
    for i in range(4):
        sources.append(
            repo.create_catalog(
                "rss_sources",
                {
                    "name": f"Source {i}",
                    "feed_url": f"https://example.org/feed/{i}",
                    "website_url": "https://example.org",
                    "is_active": True,
                },
            )
        )

    class ManyRSS:
        def entries(self, url, limit):
            return [{"title": "LLM architecture", "url": f"{url}/article/{i}"} for i in range(limit)]

    p = pipeline(db, settings)
    p.rss = ManyRSS()
    run = DiscoveryService(repo).request()
    classify = p.classify

    def interrupt(*args):
        raise RuntimeError("interrupted")

    p.classify = interrupt
    with pytest.raises(RuntimeError, match="interrupted"):
        p.discovery(run["id"])
    assert db.query("SELECT COUNT(*) n FROM article_classifications WHERE status='PENDING'")[0]["n"] == 20
    p.classify = classify
    p.discovery(run["id"])
    assert [r["n"] for r in db.query("SELECT source_id,COUNT(*) n FROM articles GROUP BY source_id")] == [
        4
    ] * 5
    assert repo.get("classification_runs", run["id"])["classified_count"] == 20
    assert db.query("SELECT COUNT(*) n FROM source_fetches")[0]["n"] == 5
