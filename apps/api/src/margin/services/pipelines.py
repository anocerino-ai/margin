"""Deterministic pipelines; external effects are injected and every unit persists independently."""

import hashlib
import html
import json
import logging
from datetime import UTC, datetime, timedelta

from margin.providers.openrouter import ModelsExhausted
from margin.repositories.core import Repository, identifier, now
from margin.runtime import runtime_settings
from margin.schemas.contracts import ClassificationResult, ContentResult
from margin.services.prompts import load_prompt


class PipelineFailure(RuntimeError):
    pass


class Pipelines:
    def __init__(self, db, settings, llm, rss, crawl, email):
        self.db, self.settings, self.llm, self.rss, self.crawl, self.email = (
            db,
            settings,
            llm,
            rss,
            crawl,
            email,
        )
        self.repo = Repository(db)

    def event(self, id, kind, stage, status, error=None):
        self.db.query(
            "INSERT INTO run_events VALUES (?,?,?,?,?,?,?)",
            [
                identifier(),
                id if kind == "DISCOVERY" else None,
                id if kind != "DISCOVERY" else None,
                stage,
                status,
                error,
                now(),
            ],
        )

    def model_used(self, operation):
        rows = self.db.query(
            "SELECT model FROM llm_attempts WHERE operation_id=? AND status='SUCCESS' ORDER BY rowid DESC LIMIT 1",
            [operation],
        )
        return rows[0]["model"] if rows else "injected-test-provider"

    def classify(self, article, run, topics):
        existing = self.db.query(
            "SELECT * FROM article_classifications WHERE article_id=? AND run_id=?",
            [article["id"], run["id"]],
        )
        if existing and existing[0]["status"] in {"CLASSIFIED", "FAILED"}:
            return
        prompt, digest = load_prompt("classification")
        id = existing[0]["id"] if existing else identifier()
        if not existing:
            self.db.query(
                "INSERT INTO article_classifications(id,article_id,run_id,status,prompt_version,prompt_hash,created_at,started_at) VALUES (?,?,?,'CLASSIFYING','v1',?,?,?)",
                [id, article["id"], run["id"], digest, now(), now()],
            )
        names = {t["topic_name"]: t for t in topics}

        def validate(result):
            labels = [m.topic for m in result.target_topics + result.non_target_topics]
            if (
                len(labels) != len(set(labels))
                or any(m.topic not in names for m in result.target_topics)
                or any(m.topic in names for m in result.non_target_topics)
            ):
                raise ValueError("TOPIC_SNAPSHOT_MISMATCH")

        try:
            result = self.llm.generate(
                prompt,
                json.dumps({"title": article["title"], "target_topics": topics}, ensure_ascii=False),
                ClassificationResult,
                id,
                "CLASSIFICATION",
                validate=validate,
            )
        except Exception as exc:
            error = (
                "CLASSIFICATION_FAILED"
                if isinstance(exc, ModelsExhausted)
                else "CLASSIFICATION_INTERNAL_ERROR"
            )
            logging.getLogger(__name__).warning(
                "Classification failed operation=%s code=%s exception_type=%s",
                id,
                error,
                type(exc).__name__,
            )
            # Errors remain failures, never converted to a non-target result.
            self.db.query(
                "UPDATE article_classifications SET status='FAILED',error_code=?,completed_at=? WHERE id=?",
                [error, now(), id],
            )
            self.event(run["id"], "DISCOVERY", "CLASSIFICATION", "FAILED", error)
            return
        target = [m for m in result.target_topics if m.confidence >= run["threshold"]]
        statements = [
            (
                "UPDATE article_classifications SET status='CLASSIFIED',is_target=?,model_used=?,completed_at=? WHERE id=?",
                [bool(target), self.model_used(id), now(), id],
            )
        ]
        for kind, matches in [("TARGET", target), ("NON_TARGET", result.non_target_topics)]:
            for position, match in enumerate(matches, 1):
                statements.append(
                    (
                        "INSERT INTO classification_topics VALUES (?,?,?,?,?,?,?)",
                        [
                            identifier(),
                            id,
                            kind,
                            names[match.topic]["topic_id"] if kind == "TARGET" else None,
                            match.topic,
                            match.confidence,
                            position,
                        ],
                    )
                )
        self.db.batch(statements)

    def discovery(self, run_id, payload=None):
        run = self.repo.get("classification_runs", run_id)
        self.db.query(
            "UPDATE classification_runs SET status='RUNNING',started_at=COALESCE(started_at,?) WHERE id=?",
            [now(), run_id],
        )
        topics = self.db.query("SELECT * FROM classification_run_topics WHERE run_id=?", [run_id])
        if payload and payload.get("article_ids"):
            for id in payload["article_ids"]:
                self.classify(self.repo.get("articles", id), run, topics)
        else:
            sources = self.db.query("SELECT * FROM rss_sources WHERE is_active=1")
            if not sources:
                raise PipelineFailure("NO_ACTIVE_SOURCES")
            # Plan one article per source per round before executing any LLM calls.
            # Commit the selection and fetch ledger together so interruption cannot skew quotas.
            candidates = []
            statements = []
            seen = set()
            for source in sorted(sources, key=lambda item: item["id"]):
                if self.db.query(
                    "SELECT id FROM source_fetches WHERE run_id=? AND source_id=?",
                    [run_id, source["id"]],
                ):
                    continue
                try:
                    entries = self.rss.entries(source["feed_url"], self.settings.max_articles_per_feed)
                except Exception:
                    statements.append(
                        (
                            "INSERT INTO source_fetches VALUES (?,?,?,'FAILED',0,'RSS_FETCH_FAILED')",
                            [identifier(), run_id, source["id"]],
                        )
                    )
                    statements.append(
                        (
                            "INSERT INTO run_events VALUES (?,?,NULL,'RSS','FAILED','RSS_FETCH_FAILED',?)",
                            [identifier(), run_id, now()],
                        )
                    )
                    continue
                fresh, known = [], 0
                for entry in entries:
                    if entry["url"] in seen or self.db.query(
                        "SELECT id FROM articles WHERE normalized_url=?", [entry["url"]]
                    ):
                        known += 1
                        continue
                    seen.add(entry["url"])
                    fresh.append(entry)
                candidates.append((source, fresh))
                statements.extend(
                    [
                        (
                            "INSERT INTO source_fetches VALUES (?,?,?,'SUCCESS',?,NULL)",
                            [identifier(), run_id, source["id"], len(entries)],
                        ),
                        (
                            "UPDATE classification_runs SET entries_found=entries_found+?,known_articles=known_articles+? WHERE id=?",
                            [len(entries), known, run_id],
                        ),
                    ]
                )
            count = self.db.query("SELECT COUNT(*) n FROM article_classifications WHERE run_id=?", [run_id])[
                0
            ]["n"]
            _, digest = load_prompt("classification")
            from margin.services.selection import balanced_entries

            for source, entry in balanced_entries(
                candidates, max(0, self.settings.max_new_articles_per_run - count)
            ):
                stamp, article_id = now(), identifier()
                statements.extend(
                    [
                        (
                            "INSERT OR IGNORE INTO articles VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [
                                article_id,
                                source["id"],
                                entry["title"],
                                entry["url"],
                                entry["url"],
                                entry.get("rss_guid"),
                                entry.get("published_at"),
                                stamp,
                                stamp,
                                stamp,
                            ],
                        ),
                        (
                            "INSERT OR IGNORE INTO article_classifications(id,article_id,run_id,status,prompt_version,prompt_hash,created_at) SELECT ?,id,?,'PENDING','v1',?,? FROM articles WHERE normalized_url=?",
                            [identifier(), run_id, digest, stamp, entry["url"]],
                        ),
                    ]
                )
            if statements:
                self.db.batch(statements)
        # Recover entries persisted before a worker interruption even if the feed has changed.
        for row in self.db.query(
            "SELECT a.* FROM articles a JOIN article_classifications c ON c.article_id=a.id WHERE c.run_id=? AND c.status IN ('PENDING','CLASSIFYING')",
            [run_id],
        ):
            self.classify(row, run, topics)
        counts = self.db.query(
            "SELECT COUNT(*) n,SUM(status='CLASSIFIED') ok,SUM(status='FAILED') failed,SUM(is_target=1) target,SUM(is_target=0) non_target FROM article_classifications WHERE run_id=?",
            [run_id],
        )[0]
        fetches = self.db.query(
            "SELECT COUNT(*) n,SUM(status='FAILED') failed FROM source_fetches WHERE run_id=?", [run_id]
        )[0]
        failed = (counts["failed"] or 0) + (fetches["failed"] or 0)
        status = "COMPLETED_WITH_ERRORS" if failed else "COMPLETED"
        if failed and not counts["ok"] and (counts["n"] or fetches["n"] == fetches["failed"]):
            status = "FAILED"
        self.db.query(
            "UPDATE classification_runs SET sources_count=?,new_articles=?,classified_count=?,failed_count=?,target_count=?,non_target_count=?,status=?,completed_at=? WHERE id=?",
            [
                fetches["n"],
                counts["n"],
                counts["ok"] or 0,
                counts["failed"] or 0,
                counts["target"] or 0,
                counts["non_target"] or 0,
                status,
                now(),
                run_id,
            ],
        )
        if runtime_settings(self.db).email_enabled:
            self.digest(run_id)

    def digest(self, run_id):
        if (
            not self.settings.email_recipient
            or not self.settings.email_from
            or not self.settings.resend_api_key.get_secret_value()
        ):
            self.event(run_id, "DISCOVERY", "EMAIL", "FAILED", "EMAIL_NOT_CONFIGURED")
            return
        rows = self.db.query("SELECT * FROM email_deliveries WHERE classification_run_id=?", [run_id])
        if not rows:
            articles = self.db.query(
                "SELECT a.title,a.url,c.is_target,c.status FROM articles a JOIN article_classifications c ON c.article_id=a.id WHERE c.run_id=?",
                [run_id],
            )
            body = (
                "<h1>Margin — Engineering digest</h1><p>" + str(len(articles)) + " articles analyzed.</p><ul>"
            )
            for a in articles:
                label = "Target" if a["is_target"] else "Failed" if a["status"] == "FAILED" else "Non-target"
                body += f'<li><b>{label}</b> — <a href="{html.escape(a["url"], quote=True)}">{html.escape(a["title"])}</a></li>'
            body += "</ul>"
            if not any(a["is_target"] for a in articles):
                body += "<p>No target articles in this run.</p>"
            id = identifier()
            self.db.query(
                "INSERT INTO email_deliveries(id,classification_run_id,provider,recipient,subject,status,created_at,content_html,sender) VALUES (?,?,'resend',?,?,'PENDING',?,?,?)",
                [
                    id,
                    run_id,
                    self.settings.email_recipient,
                    "Margin — Engineering digest",
                    now(),
                    body,
                    self.settings.email_from,
                ],
            )
            rows = self.db.query("SELECT * FROM email_deliveries WHERE id=?", [id])
        self.send_delivery(rows[0])

    def send_delivery(self, row):
        if row["status"] == "SENT":
            return
        if row.get("attempted_at") and datetime.now(UTC) - datetime.fromisoformat(
            row["attempted_at"]
        ) > timedelta(hours=23):
            raise ValueError("EMAIL_RETRY_WINDOW_EXPIRED")
        self.db.query(
            "UPDATE email_deliveries SET attempted_at=COALESCE(attempted_at,?) WHERE id=?", [now(), row["id"]]
        )
        try:
            message = self.email.send(
                row["recipient"], row["subject"], row["content_html"], f"digest/{row['id']}", row["sender"]
            )
            self.db.query(
                "UPDATE email_deliveries SET status='SENT',provider_message_id=?,sent_at=?,error_code=NULL WHERE id=?",
                [message, now(), row["id"]],
            )
        except Exception:
            self.db.query(
                "UPDATE email_deliveries SET status='FAILED',error_code='EMAIL_SEND_FAILED' WHERE id=?",
                [row["id"]],
            )
            self.event(row["classification_run_id"], "DISCOVERY", "EMAIL", "FAILED", "EMAIL_SEND_FAILED")

    def acquire(self, run):
        sources = self.db.query("SELECT * FROM generation_sources WHERE generation_run_id=?", [run["id"]])
        cache_days = runtime_settings(self.db).crawl_cache_days
        cutoff = (datetime.now(UTC) - timedelta(days=cache_days)).isoformat()
        for source in sources:
            existing = self.db.query(
                "SELECT * FROM crawl_results WHERE generation_source_id=? AND status='SUCCESS'",
                [source["id"]],
            )
            if existing:
                continue
            try:
                cached = (
                    []
                    if run["force_refresh_sources"]
                    else self.db.query(
                        "SELECT * FROM crawl_results WHERE original_url=? AND status='SUCCESS' AND crawled_at>=? ORDER BY crawled_at DESC LIMIT 1",
                        [source["original_url"], cutoff],
                    )
                )
                self.db.query(
                    "UPDATE generation_sources SET crawl_status='CRAWLING' WHERE id=?", [source["id"]]
                )
                markdown = (
                    cached[0]["content_markdown"]
                    if cached
                    else self.crawl.crawl(
                        source["original_url"], force_refresh=bool(run["force_refresh_sources"])
                    )
                )
                stamp = cached[0]["crawled_at"] if cached else now()
                self.db.batch(
                    [
                        (
                            "INSERT INTO crawl_results VALUES (?,?,'SUCCESS',?,?,?, ?,NULL)",
                            [
                                identifier(),
                                source["id"],
                                markdown,
                                hashlib.sha256(markdown.encode()).hexdigest(),
                                stamp,
                                source["original_url"],
                            ],
                        ),
                        ("UPDATE generation_sources SET crawl_status='SUCCESS' WHERE id=?", [source["id"]]),
                    ]
                )
            except Exception:
                self.db.batch(
                    [
                        (
                            "INSERT INTO crawl_results VALUES (?,?,'FAILED',NULL,NULL,?,?,'CRAWL_FAILED')",
                            [identifier(), source["id"], now(), source["original_url"]],
                        ),
                        ("UPDATE generation_sources SET crawl_status='FAILED' WHERE id=?", [source["id"]]),
                    ]
                )
                self.event(run["id"], "GENERATION", "CRAWL", "FAILED", "CRAWL_FAILED")
        return self.db.query(
            "SELECT c.*,s.article_title FROM crawl_results c JOIN generation_sources s ON s.id=c.generation_source_id WHERE s.generation_run_id=? AND c.status='SUCCESS' AND c.rowid=(SELECT MAX(c2.rowid) FROM crawl_results c2 WHERE c2.generation_source_id=s.id AND c2.status='SUCCESS')",
            [run["id"]],
        )

    def create_version(self, output, snapshots, operation, instructions="", dependency=None):
        existing = self.db.query("SELECT id FROM generation_versions WHERE operation_id=?", [operation])
        if existing:
            return existing[0]["id"]
        if not snapshots:
            raise PipelineFailure("NO_VALID_SOURCES")
        # No silent truncation: oversize context fails visibly, preserving complete evidence.
        total = sum(len(s["content_markdown"]) for s in snapshots) + (
            len(dependency["content_markdown"]) if dependency else 0
        )
        if total > self.settings.context_char_budget:
            raise PipelineFailure("CONTEXT_BUDGET_EXCEEDED")
        kind = output["output_type"].lower()
        prompt, digest = load_prompt(kind)
        context = {
            "sources": [
                {
                    "url": s["original_url"],
                    "title": s.get("article_title", ""),
                    "markdown": s["content_markdown"],
                }
                for s in snapshots
            ],
            "additional_instructions": instructions,
            "blog": dependency["content_markdown"] if dependency else None,
        }
        result = self.llm.generate(
            prompt,
            json.dumps(context, ensure_ascii=False),
            ContentResult,
            operation,
            output["output_type"] + "_GENERATION",
        )
        id = identifier()
        number = self.db.query(
            "SELECT COALESCE(MAX(version),0)+1 n FROM generation_versions WHERE generation_output_id=?",
            [output["id"]],
        )[0]["n"]
        statements = [
            (
                "INSERT INTO generation_versions(id,generation_output_id,version,title,content_markdown,additional_instructions,model_used,prompt_version,prompt_hash,status,created_at,operation_id) VALUES (?,?,?,?,?,?,?,?,?,'DRAFT',?,?)",
                [
                    id,
                    output["id"],
                    number,
                    result.title,
                    result.content_markdown,
                    instructions,
                    self.model_used(operation),
                    "v2",
                    digest,
                    now(),
                    operation,
                ],
            )
        ]
        for source in snapshots:
            estimate = (len(source["content_markdown"]) + 3) // 4
            statements.append(
                (
                    "INSERT INTO generation_version_sources VALUES (?,?,'FULL',?,?,?)",
                    [id, source["id"], source["content_markdown"], estimate, estimate],
                )
            )
        if dependency:
            statements.append(
                (
                    "INSERT INTO generation_version_dependencies VALUES (?,?,'GENERATED_FROM')",
                    [id, dependency["id"]],
                )
            )
        self.db.batch(statements)
        return id

    def generation(self, run_id):
        run = self.repo.get("generation_runs", run_id)
        self.db.query(
            "UPDATE generation_runs SET status='CRAWLING',started_at=COALESCE(started_at,?) WHERE id=?",
            [now(), run_id],
        )
        snapshots = self.acquire(run)
        if not snapshots:
            raise PipelineFailure("NO_VALID_SOURCES")
        self.db.query("UPDATE generation_runs SET status='GENERATING' WHERE id=?", [run_id])
        outputs = self.db.query(
            "SELECT * FROM generation_outputs WHERE generation_run_id=? ORDER BY output_type", [run_id]
        )
        blog = None
        failures = 0
        for output in outputs:
            try:
                if output["output_type"] == "LINKEDIN" and run["generate_blog"] and not blog:
                    raise PipelineFailure("BLOG_DEPENDENCY_FAILED")
                id = self.create_version(output, snapshots, output["id"] + "/initial", dependency=blog)
                if output["output_type"] == "BLOG":
                    blog = self.db.query("SELECT * FROM generation_versions WHERE id=?", [id])[0]
                self.event(run_id, "GENERATION", output["output_type"], "SUCCESS")
            except Exception as exc:
                failures += 1
                self.event(
                    run_id,
                    "GENERATION",
                    output["output_type"],
                    "FAILED",
                    str(exc) if isinstance(exc, PipelineFailure) else "GENERATION_FAILED",
                )
        crawls_failed = self.db.query(
            "SELECT COUNT(*) n FROM generation_sources WHERE generation_run_id=? AND crawl_status='FAILED'",
            [run_id],
        )[0]["n"]
        status = (
            "FAILED"
            if failures == len(outputs)
            else "COMPLETED_WITH_ERRORS"
            if failures or crawls_failed
            else "COMPLETED"
        )
        self.db.query(
            "UPDATE generation_runs SET status=?,completed_at=? WHERE id=?", [status, now(), run_id]
        )

    def regenerate(self, output_id, payload, operation):
        output = self.db.query("SELECT * FROM generation_outputs WHERE id=?", [output_id])[0]
        previous = self.db.query(
            "SELECT * FROM generation_versions WHERE generation_output_id=? ORDER BY version DESC LIMIT 1",
            [output_id],
        )
        if not previous:
            raise PipelineFailure("NO_PREVIOUS_VERSION")
        snapshots = self.db.query(
            "SELECT c.* FROM crawl_results c JOIN generation_version_sources s ON s.crawl_result_id=c.id WHERE s.version_id=?",
            [previous[0]["id"]],
        )
        dependency = None
        dependency_id = payload.get("depends_on_version_id")
        if not dependency_id:
            old = self.db.query(
                "SELECT depends_on_version_id FROM generation_version_dependencies WHERE version_id=?",
                [previous[0]["id"]],
            )
            dependency_id = old[0]["depends_on_version_id"] if old else None
        if dependency_id:
            dependencies = self.db.query(
                "SELECT v.* FROM generation_versions v JOIN generation_outputs o ON o.id=v.generation_output_id WHERE v.id=? AND o.output_type='BLOG' AND o.generation_run_id=?",
                [dependency_id, output["generation_run_id"]],
            )
            if output["output_type"] != "LINKEDIN" or not dependencies:
                raise PipelineFailure("INVALID_BLOG_DEPENDENCY")
            dependency = dependencies[0]
        self.create_version(
            output, snapshots, operation, payload.get("additional_instructions", ""), dependency
        )
