CREATE UNIQUE INDEX one_active_regeneration ON job_outbox (json_extract(payload,'$.output_id')) WHERE kind='REGENERATION' AND status IN ('PENDING','RUNNING');
