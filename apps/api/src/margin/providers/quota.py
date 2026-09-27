"""Persistent request reservations shared by workers using the same database."""

import json
import time
from datetime import UTC, datetime, timedelta


class QuotaDeferred(RuntimeError):
    pass


def pause_until(db, until, reason):
    db.query(
        "INSERT INTO app_settings(key,value,updated_at) VALUES ('llm.quota_pause',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
        [json.dumps({"until": until, "reason": reason}), datetime.now(UTC).isoformat()],
    )


def paused(db, clock=time.time):
    rows = db.query("SELECT value FROM app_settings WHERE key='llm.quota_pause'")
    state = json.loads(rows[0]["value"]) if rows else {}
    return state if state.get("until", 0) > clock() else None


class RequestQuota:
    def __init__(self, db, limits, sleep=time.sleep, clock=time.time):
        self.db, self.limits, self.sleep, self.clock = db, limits, sleep, clock

    def next_day(self):
        return (
            datetime.fromtimestamp(self.clock(), UTC).replace(hour=0, minute=0, second=5, microsecond=0)
            + timedelta(days=1)
        ).timestamp()

    def reserve(self):
        while True:
            if paused(self.db, self.clock):
                raise QuotaDeferred("OPENROUTER_QUOTA_PAUSED")
            rpm, rpd = self.limits()
            stamp = self.clock()
            day = datetime.fromtimestamp(stamp, UTC).date().isoformat()
            # One atomic UPDATE reserves both daily budget and the next request slot.
            self.db.query(
                "INSERT OR IGNORE INTO app_settings(key,value,updated_at) VALUES ('llm.request_budget','{}',?)",
                [day],
            )
            rows = self.db.query(
                "UPDATE app_settings SET value=json_object('day',?,'count',CASE WHEN json_extract(value,'$.day')=? THEN COALESCE(json_extract(value,'$.count'),0)+1 ELSE 1 END,'last',?),updated_at=? WHERE key='llm.request_budget' AND (COALESCE(json_extract(value,'$.day'),'')!=? OR COALESCE(json_extract(value,'$.count'),0)<?) AND COALESCE(json_extract(value,'$.last'),0)<=? RETURNING value",
                [day, day, stamp, day, day, rpd, stamp - 60.0 / rpm],
            )
            if rows:
                return
            state = json.loads(
                self.db.query("SELECT value FROM app_settings WHERE key='llm.request_budget'")[0]["value"]
            )
            if state.get("day") == day and state.get("count", 0) >= rpd:
                pause_until(self.db, self.next_day(), "DAILY_REQUEST_BUDGET")
                raise QuotaDeferred("DAILY_REQUEST_BUDGET")
            self.sleep(min(20, max(0.01, state.get("last", 0) + 60.0 / rpm - self.clock())))
