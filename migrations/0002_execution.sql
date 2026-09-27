ALTER TABLE job_outbox ADD COLUMN payload TEXT NOT NULL DEFAULT '{}';
ALTER TABLE job_outbox ADD COLUMN owner TEXT;
ALTER TABLE job_outbox ADD COLUMN lease_until TEXT;
ALTER TABLE job_outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE job_outbox ADD COLUMN error_code TEXT;
ALTER TABLE job_outbox ADD COLUMN completed_at TEXT;
CREATE TABLE worker_guards (job_id TEXT PRIMARY KEY, owner TEXT NOT NULL);
CREATE TRIGGER validate_worker_guard BEFORE INSERT ON worker_guards BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM job_outbox WHERE id=NEW.job_id AND owner=NEW.owner AND status='RUNNING' AND julianday(lease_until)>julianday('now')) THEN RAISE(ABORT,'JOB_LEASE_LOST') END;
END;
CREATE TABLE worker_status (id TEXT PRIMARY KEY, heartbeat_at TEXT NOT NULL);
CREATE TABLE source_fetches (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES classification_runs(id), source_id TEXT NOT NULL REFERENCES rss_sources(id), status TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED')), entries_count INTEGER NOT NULL DEFAULT 0, error_code TEXT, UNIQUE(run_id,source_id));
ALTER TABLE email_deliveries ADD COLUMN content_html TEXT;
ALTER TABLE email_deliveries ADD COLUMN sender TEXT;
ALTER TABLE email_deliveries ADD COLUMN attempted_at TEXT;
CREATE UNIQUE INDEX one_digest_per_run ON email_deliveries(classification_run_id);
ALTER TABLE generation_versions ADD COLUMN operation_id TEXT;
CREATE UNIQUE INDEX generation_operation_once ON generation_versions(operation_id) WHERE operation_id IS NOT NULL;
