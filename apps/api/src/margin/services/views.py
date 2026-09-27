from math import ceil


def article_view(db, row):
    item = dict(row)
    item["source_name"] = db.query("SELECT name FROM rss_sources WHERE id=?", [row["source_id"]])[0]["name"]
    matches = db.query(
        "SELECT * FROM article_classifications WHERE article_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
        [row["id"]],
    )
    item["classification"] = matches[0] if matches else None
    if matches:
        item["classification"]["topics"] = db.query(
            "SELECT * FROM classification_topics WHERE classification_id=? ORDER BY topic_type,position",
            [matches[0]["id"]],
        )
    return item


def articles(
    db,
    page,
    page_size,
    search="",
    source=None,
    classification=None,
    topic=None,
    run_id=None,
    date_from=None,
    date_to=None,
):
    clauses = ["a.title LIKE ?"]
    params = ["%" + search + "%"]
    if source:
        clauses.append("a.source_id=?")
        params.append(source)
    if date_from:
        clauses.append("date(a.published_at)>=date(?)")
        params.append(str(date_from))
    if date_to:
        clauses.append("date(a.published_at)<=date(?)")
        params.append(str(date_to))
    if run_id:
        clauses.append(
            "EXISTS (SELECT 1 FROM article_classifications rc WHERE rc.article_id=a.id AND rc.run_id=?)"
        )
        params.append(run_id)
    latest = "c.rowid=(SELECT MAX(c2.rowid) FROM article_classifications c2 WHERE c2.article_id=a.id)"
    if classification:
        condition = {"target": "c.is_target=1", "non-target": "c.is_target=0", "failed": "c.status='FAILED'"}[
            classification
        ]
        clauses.append(
            "EXISTS (SELECT 1 FROM article_classifications c WHERE c.article_id=a.id AND "
            + latest
            + " AND "
            + condition
            + ")"
        )
    if topic:
        clauses.append(
            "EXISTS (SELECT 1 FROM classification_topics t JOIN article_classifications c ON c.id=t.classification_id WHERE c.article_id=a.id AND "
            + latest
            + " AND t.topic_name=?)"
        )
        params.append(topic)
    where = " AND ".join(clauses)
    total = db.query("SELECT COUNT(*) n FROM articles a WHERE " + where, params)[0]["n"]
    rows = db.query(
        "SELECT a.* FROM articles a WHERE " + where + " ORDER BY a.discovered_at DESC,a.id LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    )
    return {
        "items": [article_view(db, r) for r in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size),
        },
    }


def generation_detail(repo, id):
    db = repo.db
    result = repo.get("generation_runs", id)
    result["sources"] = db.query("SELECT s.* FROM generation_sources s WHERE generation_run_id=?", [id])
    for source in result["sources"]:
        source["crawls"] = db.query(
            "SELECT id,status,crawled_at,content_hash,error_code FROM crawl_results WHERE generation_source_id=? ORDER BY rowid",
            [source["id"]],
        )
    result["outputs"] = db.query(
        "SELECT * FROM generation_outputs WHERE generation_run_id=? ORDER BY output_type", [id]
    )
    for output in result["outputs"]:
        output["versions"] = db.query(
            "SELECT * FROM generation_versions WHERE generation_output_id=? ORDER BY version", [output["id"]]
        )
        for version in output["versions"]:
            version["dependencies"] = db.query(
                "SELECT d.depends_on_version_id,v.version,o.output_type FROM generation_version_dependencies d JOIN generation_versions v ON v.id=d.depends_on_version_id JOIN generation_outputs o ON o.id=v.generation_output_id WHERE d.version_id=?",
                [version["id"]],
            )
            version["sources"] = db.query(
                "SELECT s.crawl_result_id,s.context_mode,s.original_tokens,s.context_tokens,c.original_url,c.content_hash FROM generation_version_sources s JOIN crawl_results c ON c.id=s.crawl_result_id WHERE s.version_id=?",
                [version["id"]],
            )
    result["events"] = db.query(
        "SELECT * FROM run_events WHERE generation_run_id=? ORDER BY created_at", [id]
    )
    result["jobs"] = db.query(
        "SELECT id,kind,status,error_code,created_at FROM job_outbox WHERE resource_id=? OR (kind='REGENERATION' AND json_extract(payload,'$.output_id') IN (SELECT id FROM generation_outputs WHERE generation_run_id=?)) ORDER BY created_at",
        [id, id],
    )
    return result
