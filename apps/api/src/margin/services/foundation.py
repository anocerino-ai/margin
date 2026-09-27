from margin.providers.jobs import OutboxDispatcher
from margin.repositories.core import NotFound, Repository, identifier, now
from margin.schemas.contracts import GenerationCreate


class Conflict(Exception):
    pass


class GenerationService:
    def __init__(self, repo: Repository, dispatcher=None):
        self.repo = repo
        self.dispatcher = dispatcher or OutboxDispatcher()

    def create(self, request: GenerationCreate):
        articles = [self.repo.get("articles", id) for id in request.article_ids]
        id, stamp = identifier(), now()
        statements = [
            (
                "INSERT INTO generation_runs(id,status,generate_blog,generate_linkedin,force_refresh_sources,created_at) VALUES (?,'PENDING',?,?,?,?)",
                [
                    id,
                    "BLOG" in request.outputs,
                    "LINKEDIN" in request.outputs,
                    request.force_refresh_sources,
                    stamp,
                ],
            )
        ]
        for article in articles:
            statements.append(
                (
                    "INSERT INTO generation_sources(id,generation_run_id,article_id,original_url,article_title,selected_at) VALUES (?,?,?,?,?,?)",
                    [identifier(), id, article["id"], article["url"], article["title"], stamp],
                )
            )
        for kind in request.outputs:
            statements.append(
                ("INSERT INTO generation_outputs VALUES (?,?,?,?)", [identifier(), id, kind, stamp])
            )
        statements.append(self.dispatcher.enqueue_statement("GENERATION", id))
        self.repo.db.batch(statements)
        return {"id": id, "status": "PENDING"}

    def approve(self, output_id, version):
        rows = self.repo.db.query(
            "SELECT * FROM generation_versions WHERE generation_output_id=? AND version=?",
            [output_id, version],
        )
        if not rows:
            raise NotFound("VERSION_NOT_FOUND")
        chosen = rows[0]
        # One transaction: a failed approval cannot erase the previous approved version.
        self.repo.db.batch(
            [
                (
                    "UPDATE generation_versions SET status='ARCHIVED' WHERE generation_output_id=? AND status='APPROVED' AND id!=?",
                    [output_id, chosen["id"]],
                ),
                (
                    "UPDATE generation_versions SET status='APPROVED',approved_at=COALESCE(approved_at,?) WHERE id=?",
                    [now(), chosen["id"]],
                ),
            ]
        )
        return self.repo.db.query("SELECT * FROM generation_versions WHERE id=?", [chosen["id"]])[0]


class DiscoveryService:
    def __init__(self, repo: Repository, dispatcher=None):
        self.repo = repo
        self.dispatcher = dispatcher or OutboxDispatcher()

    def request(self, trigger="MANUAL", schedule_slot=None, payload=None):
        id, stamp = identifier(), now()
        settings = self.repo.db.query("SELECT value FROM app_settings WHERE key='classification.threshold'")
        threshold = float(settings[0]["value"]) if settings else 0.7
        self.repo.db.batch(
            [
                (
                    "INSERT INTO classification_runs(id,trigger_type,status,schedule_slot,threshold,created_at) VALUES (?,?,'PENDING',?,?,?)",
                    [id, trigger, schedule_slot, threshold, stamp],
                ),
                (
                    "INSERT INTO classification_run_topics SELECT ?,id,name,description FROM topics WHERE is_active=1",
                    [id],
                ),
                self.dispatcher.enqueue_statement("DISCOVERY", id, payload),
            ]
        )
        return {"id": id, "status": "PENDING"}
