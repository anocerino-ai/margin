"""Durable lease worker. Run separately from the HTTP process."""

import argparse
import json
import threading
import time
from datetime import UTC, datetime, timedelta

from margin.config import Settings
from margin.providers.email import ResendProvider
from margin.providers.firecrawl import FirecrawlProvider
from margin.providers.openrouter import OpenRouterProvider
from margin.providers.rss import RSSProvider
from margin.repositories.core import identifier, now
from margin.runtime import open_database
from margin.security import load_credentials
from margin.services.pipelines import Pipelines


class FencedDatabase:
    def __init__(self, db, id, owner):
        self.db, self.id, self.owner = db, id, owner

    def query(self, sql, params=None):
        return self.batch([(sql, params or [])])[0]

    def batch(self, statements):
        return self.db.batch(
            [
                ("INSERT INTO worker_guards VALUES (?,?)", [self.id, self.owner]),
                *statements,
                ("DELETE FROM worker_guards WHERE job_id=?", [self.id]),
            ]
        )[1:-1]


def lease_until():
    return (datetime.now(UTC) + timedelta(minutes=3)).isoformat()


class Worker:
    def __init__(self, db, settings, pipeline_factory=None):
        self.db, self.settings, self.owner = db, settings, identifier()
        self.factory = pipeline_factory or self.make_pipeline

    def make_pipeline(self, db):
        load_credentials(self.settings)
        return Pipelines(
            db,
            self.settings,
            OpenRouterProvider(
                db,
                self.settings.openrouter_api_key.get_secret_value(),
                max_output_tokens=self.settings.llm_max_output_tokens,
            ),
            RSSProvider(),
            FirecrawlProvider(self.settings.firecrawl_api_key.get_secret_value()),
            ResendProvider(self.settings.resend_api_key.get_secret_value()),
        )

    def heartbeat(self):
        self.db.query(
            "INSERT INTO worker_status VALUES (?,?) ON CONFLICT(id) DO UPDATE SET heartbeat_at=excluded.heartbeat_at",
            [self.owner, now()],
        )

    def claim(self):
        self.heartbeat()
        return self.db.query(
            """UPDATE job_outbox SET status='RUNNING',owner=?,lease_until=?,attempts=attempts+1
        WHERE id=(SELECT id FROM job_outbox WHERE status='PENDING' OR (status='RUNNING' AND julianday(lease_until)<julianday('now')) ORDER BY created_at LIMIT 1)
        RETURNING *""",
            [self.owner, lease_until()],
        )

    def once(self):
        jobs = self.claim()
        if not jobs:
            return False
        job = jobs[0]
        stop = threading.Event()

        def renew():
            while not stop.wait(20):
                try:
                    self.db.query(
                        "UPDATE job_outbox SET lease_until=? WHERE id=? AND owner=? AND status='RUNNING'",
                        [lease_until(), job["id"], self.owner],
                    )
                    self.heartbeat()
                except Exception:
                    return

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
        fenced = FencedDatabase(self.db, job["id"], self.owner)
        try:
            if job["attempts"] > 3:
                raise RuntimeError("WORKER_RETRY_LIMIT")
            pipeline = self.factory(fenced)
            payload = json.loads(job["payload"])
            if job["kind"] == "DISCOVERY":
                pipeline.discovery(job["resource_id"], payload)
            elif job["kind"] == "GENERATION":
                pipeline.generation(job["resource_id"])
            elif job["kind"] == "REGENERATION":
                pipeline.regenerate(payload["output_id"], payload, job["resource_id"])
            fenced.query(
                "UPDATE job_outbox SET status='COMPLETED',completed_at=?,lease_until=NULL WHERE id=?",
                [now(), job["id"]],
            )
        except Exception:
            # A stale owner cannot mark another worker's job or resource failed.
            try:
                statements = []
                if job["kind"] in {"DISCOVERY", "GENERATION"}:
                    table = "classification_runs" if job["kind"] == "DISCOVERY" else "generation_runs"
                    statements.append(
                        (
                            f"UPDATE {table} SET status='FAILED',completed_at=? WHERE id=?",
                            [now(), job["resource_id"]],
                        )
                    )
                statements.append(
                    (
                        "UPDATE job_outbox SET status='FAILED',error_code='JOB_EXECUTION_FAILED',completed_at=?,lease_until=NULL WHERE id=?",
                        [now(), job["id"]],
                    )
                )
                fenced.batch(statements)
            except Exception:
                pass
        finally:
            stop.set()
            thread.join(timeout=1)
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one pending job")
    parser.add_argument("--drain", action="store_true", help="Process pending jobs then exit")
    args = parser.parse_args()
    settings = Settings()
    db = open_database(settings)
    worker = Worker(db, settings)
    try:
        while True:
            worked = worker.once()
            if args.once or args.drain and not worked:
                break
            if not worked:
                time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        db.close()


if __name__ == "__main__":
    main()
