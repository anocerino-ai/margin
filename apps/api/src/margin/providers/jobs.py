import json

from margin.repositories.core import identifier, now


class OutboxDispatcher:
    """Enqueue inside the resource transaction. Consumed by the separate lease worker."""

    def enqueue_statement(self, kind, resource_id, payload=None):
        return (
            "INSERT INTO job_outbox(id,kind,resource_id,created_at,payload) VALUES (?,?,?,?,?)",
            [identifier(), kind, resource_id, now(), json.dumps(payload or {})],
        )
