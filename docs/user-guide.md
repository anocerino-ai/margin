# First discovery and draft

## 1. Prepare the workspace

Confirm the worker is online, at least one source and topic are active, OpenRouter is configured, and at least one supported model is enabled. Firecrawl is needed later for generation. Topics describe what you want to follow; changes affect future classification snapshots, not history.

## 2. Run discovery manually

Use **Run discovery now** in Settings or the Discovery page. Save any runtime settings first: the manual command uses saved configuration. It does not require D1 or a scheduled workflow.

The API queues a job; the separate worker fetches feeds, normalizes URLs, deduplicates known articles and classifies titles. New article limits bound the initial workload. Classification can match target topics, identify non-target topics or fail. A failed classification is not equivalent to a non-target result.

The run detail shows status, article counts, events and email outcomes. Partial source failures do not erase successful work. Repeating discovery generally skips already-known URLs; use an article's reclassification action when you explicitly want another classification.

## 3. Explore the library

Filter by source, classification status, topic or discovery date. Open an article to inspect its original URL, classification and provenance. You can promote a non-target topic for future runs or retry classification.

Select one or more articles to create a generation. Library articles are source records, not already-generated drafts.

## 4. Generate

Choose Blog, LinkedIn or both. Optionally request fresh source extraction. This action uses Firecrawl and OpenRouter and consumes provider quotas.

The worker gathers source snapshots and prepares context. When both outputs are requested, LinkedIn uses the generated blog version as a dependency. Standalone LinkedIn output is also supported. New drafts use English v2 prompts. Historical v1 prompts remain unchanged for provenance.

Watch status and Processing events. Context above the configured character budget fails visibly rather than silently truncating sources. There is no automatic summarization stage in this version; choose fewer or shorter sources for a new request.

## 5. Review and revise

Read the rendered draft or Markdown, inspect sources, and check model/prompt metadata. Regeneration adds a new immutable version; it does not overwrite the previous one. When regenerating LinkedIn you can select the blog version it depends on.

Approval marks a version as reviewed. It does not publish to LinkedIn or a blog. Copy/export the content manually and check attribution, factual claims and destination formatting before publication.

## Scheduling

Settings store a daily or weekly schedule and timezone. Automatic wakeups require the remote [GitHub Actions setup](github-actions.md). A local worker alone processes queued jobs; it does not create scheduled discovery jobs. Manual discovery remains available independently.
