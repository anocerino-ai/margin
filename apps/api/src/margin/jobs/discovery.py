"""Scheduler foundation: evaluates due dates; execution is gated until M4."""

import argparse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def due_slot(now: datetime, frequency="WEEKLY", day=0, hour=8, minute=0, timezone_name="Europe/Rome"):
    local = now.astimezone(ZoneInfo(timezone_name))
    scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == "WEEKLY":
        scheduled -= timedelta(days=(local.weekday() - day) % 7)
        if scheduled > local:
            scheduled -= timedelta(days=7)
    elif frequency == "DAILY":
        if scheduled > local:
            scheduled -= timedelta(days=1)
    else:
        raise ValueError("Unsupported frequency")
    return scheduled.astimezone(UTC).isoformat()


def main():
    from margin.config import Settings
    from margin.jobs.worker import Worker
    from margin.repositories.core import Repository
    from margin.runtime import open_database, require_ready, runtime_settings
    from margin.services.foundation import DiscoveryService

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    db = open_database(settings)
    try:
        schedule = runtime_settings(db).discovery
        slot = due_slot(
            datetime.now(UTC),
            schedule.frequency,
            schedule.day_of_week,
            schedule.hour,
            schedule.minute,
            schedule.timezone,
        )
        already = db.query("SELECT id FROM classification_runs WHERE schedule_slot=?", [slot])
        if args.dry_run:
            print({"enabled": schedule.enabled, "slot": slot, "already_requested": bool(already)})
            return
        if settings.storage == "sqlite":
            raise SystemExit(
                "Scheduled discovery requires shared remote D1 storage; use manual API for local runs."
            )
        if not schedule.enabled or already:
            print("Discovery not due.")
        else:
            require_ready(db, settings, "DISCOVERY")
            active = db.query("SELECT id FROM classification_runs WHERE status IN ('PENDING','RUNNING')")
            if not active:
                DiscoveryService(Repository(db)).request("SCHEDULED", slot)
        worker = Worker(db, settings)
        while worker.once():
            pass
    finally:
        db.close()


if __name__ == "__main__":
    main()
