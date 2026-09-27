CREATE TABLE rss_sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, feed_url TEXT UNIQUE,
 website_url TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(is_active = 0 OR feed_url IS NOT NULL)
);
CREATE TABLE topics (
 id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, description TEXT NOT NULL DEFAULT '',
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE classification_runs (
 id TEXT PRIMARY KEY, trigger_type TEXT NOT NULL CHECK(trigger_type IN ('MANUAL','SCHEDULED','RETRY')),
 status TEXT NOT NULL CHECK(status IN ('PENDING','RUNNING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED')),
 schedule_slot TEXT UNIQUE, threshold REAL NOT NULL CHECK(threshold BETWEEN 0 AND 1),
 started_at TEXT, completed_at TEXT, created_at TEXT NOT NULL,
 sources_count INTEGER NOT NULL DEFAULT 0, entries_found INTEGER NOT NULL DEFAULT 0,
 known_articles INTEGER NOT NULL DEFAULT 0, new_articles INTEGER NOT NULL DEFAULT 0,
 classified_count INTEGER NOT NULL DEFAULT 0, failed_count INTEGER NOT NULL DEFAULT 0,
 target_count INTEGER NOT NULL DEFAULT 0, non_target_count INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX one_active_discovery ON classification_runs ((1)) WHERE status IN ('PENDING','RUNNING');
CREATE TABLE classification_run_topics (
 run_id TEXT NOT NULL REFERENCES classification_runs(id), topic_id TEXT NOT NULL REFERENCES topics(id),
 topic_name TEXT NOT NULL, topic_description TEXT NOT NULL, PRIMARY KEY(run_id,topic_id)
);
CREATE TABLE articles (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES rss_sources(id), title TEXT NOT NULL,
 url TEXT NOT NULL, normalized_url TEXT NOT NULL UNIQUE, rss_guid TEXT,
 published_at TEXT, discovered_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX articles_published ON articles(published_at DESC);
CREATE TABLE article_classifications (
 id TEXT PRIMARY KEY, article_id TEXT NOT NULL REFERENCES articles(id), run_id TEXT NOT NULL REFERENCES classification_runs(id),
 status TEXT NOT NULL CHECK(status IN ('PENDING','CLASSIFYING','CLASSIFIED','FAILED')),
 is_target INTEGER CHECK(is_target IN (0,1)), model_used TEXT, prompt_version TEXT NOT NULL,
 prompt_hash TEXT NOT NULL, started_at TEXT, completed_at TEXT, error_code TEXT, error_message TEXT,
 created_at TEXT NOT NULL, UNIQUE(article_id,run_id),
 CHECK((status='CLASSIFIED' AND is_target IS NOT NULL) OR (status!='CLASSIFIED' AND is_target IS NULL))
);
CREATE INDEX classifications_article ON article_classifications(article_id,created_at DESC);
CREATE TABLE classification_topics (
 id TEXT PRIMARY KEY, classification_id TEXT NOT NULL REFERENCES article_classifications(id),
 topic_type TEXT NOT NULL CHECK(topic_type IN ('TARGET','NON_TARGET')),
 target_topic_id TEXT REFERENCES topics(id), topic_name TEXT NOT NULL,
 confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 3),
 UNIQUE(classification_id,topic_type,position),
 CHECK((topic_type='TARGET' AND target_topic_id IS NOT NULL) OR (topic_type='NON_TARGET' AND target_topic_id IS NULL))
);
CREATE TABLE generation_runs (
 id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('PENDING','CRAWLING','PREPARING_CONTEXT','GENERATING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED')),
 generate_blog INTEGER NOT NULL CHECK(generate_blog IN (0,1)), generate_linkedin INTEGER NOT NULL CHECK(generate_linkedin IN (0,1)),
 force_refresh_sources INTEGER NOT NULL DEFAULT 0 CHECK(force_refresh_sources IN (0,1)),
 created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, CHECK(generate_blog + generate_linkedin > 0)
);
CREATE TABLE generation_sources (
 id TEXT PRIMARY KEY, generation_run_id TEXT NOT NULL REFERENCES generation_runs(id), article_id TEXT NOT NULL REFERENCES articles(id),
 original_url TEXT NOT NULL, article_title TEXT NOT NULL,
 crawl_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(crawl_status IN ('PENDING','CRAWLING','SUCCESS','FAILED')),
 selected_at TEXT NOT NULL, UNIQUE(generation_run_id,article_id)
);
CREATE TABLE crawl_results (
 id TEXT PRIMARY KEY, generation_source_id TEXT NOT NULL REFERENCES generation_sources(id),
 status TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED')), content_markdown TEXT, content_hash TEXT,
 crawled_at TEXT NOT NULL, original_url TEXT NOT NULL, error_code TEXT,
 CHECK(status != 'SUCCESS' OR (content_markdown IS NOT NULL AND content_hash IS NOT NULL))
);
CREATE TABLE generation_outputs (
 id TEXT PRIMARY KEY, generation_run_id TEXT NOT NULL REFERENCES generation_runs(id),
 output_type TEXT NOT NULL CHECK(output_type IN ('BLOG','LINKEDIN')), created_at TEXT NOT NULL,
 UNIQUE(generation_run_id,output_type)
);
CREATE TABLE generation_versions (
 id TEXT PRIMARY KEY, generation_output_id TEXT NOT NULL REFERENCES generation_outputs(id),
 version INTEGER NOT NULL CHECK(version > 0), title TEXT NOT NULL, content_markdown TEXT NOT NULL,
 additional_instructions TEXT NOT NULL DEFAULT '', model_used TEXT NOT NULL, prompt_version TEXT NOT NULL,
 prompt_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('DRAFT','APPROVED','ARCHIVED')),
 created_at TEXT NOT NULL, approved_at TEXT, UNIQUE(generation_output_id,version)
);
CREATE UNIQUE INDEX one_approved_version ON generation_versions(generation_output_id) WHERE status='APPROVED';
CREATE TRIGGER immutable_version BEFORE UPDATE OF content_markdown,title,model_used,prompt_version,prompt_hash,additional_instructions,version,generation_output_id ON generation_versions
BEGIN SELECT RAISE(ABORT,'Generation content is immutable; append a version'); END;
CREATE TABLE generation_version_dependencies (
 version_id TEXT NOT NULL REFERENCES generation_versions(id), depends_on_version_id TEXT NOT NULL REFERENCES generation_versions(id),
 dependency_type TEXT NOT NULL DEFAULT 'GENERATED_FROM', PRIMARY KEY(version_id,depends_on_version_id), CHECK(version_id != depends_on_version_id)
);
CREATE TABLE generation_version_sources (
 version_id TEXT NOT NULL REFERENCES generation_versions(id), crawl_result_id TEXT NOT NULL REFERENCES crawl_results(id),
 context_mode TEXT NOT NULL CHECK(context_mode IN ('FULL','SUMMARIZED')), context_markdown TEXT NOT NULL,
 original_tokens INTEGER NOT NULL CHECK(original_tokens>=0), context_tokens INTEGER NOT NULL CHECK(context_tokens>=0),
 PRIMARY KEY(version_id,crawl_result_id)
);
CREATE TABLE llm_attempts (
 id TEXT PRIMARY KEY, operation_type TEXT NOT NULL CHECK(operation_type IN ('CLASSIFICATION','BLOG_GENERATION','LINKEDIN_GENERATION','SUMMARY')),
 operation_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, attempt_number INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('SUCCESS','HTTP_ERROR','INVALID_OUTPUT','TIMEOUT')),
 started_at TEXT NOT NULL, completed_at TEXT NOT NULL, error_code TEXT,
 UNIQUE(operation_type,operation_id,attempt_number)
);
CREATE TABLE email_deliveries (
 id TEXT PRIMARY KEY, classification_run_id TEXT NOT NULL REFERENCES classification_runs(id),
 provider TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PENDING','SENT','FAILED')), provider_message_id TEXT,
 sent_at TEXT, error_code TEXT, created_at TEXT NOT NULL
);
CREATE TABLE run_events (
 id TEXT PRIMARY KEY, classification_run_id TEXT REFERENCES classification_runs(id),
 generation_run_id TEXT REFERENCES generation_runs(id), stage TEXT NOT NULL, status TEXT NOT NULL,
 error_code TEXT, created_at TEXT NOT NULL,
 CHECK((classification_run_id IS NULL) != (generation_run_id IS NULL))
);
CREATE TABLE llm_models (
 id TEXT PRIMARY KEY, model TEXT NOT NULL UNIQUE, position INTEGER NOT NULL UNIQUE,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))
);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL CHECK(json_valid(value)), updated_at TEXT NOT NULL);
CREATE TABLE job_outbox (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('DISCOVERY','GENERATION','REGENERATION')),
 resource_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','RUNNING','COMPLETED','FAILED')),
 created_at TEXT NOT NULL, UNIQUE(kind,resource_id)
);
