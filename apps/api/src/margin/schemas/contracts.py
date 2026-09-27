from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorInfo(Contract):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(Contract):
    error: ErrorInfo


class Pagination(Contract):
    page: int
    page_size: int
    total: int
    pages: int


T = TypeVar("T")


class Page(Contract, Generic[T]):
    items: list[T]
    pagination: Pagination


class TopicCreate(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    is_active: bool = True


class TopicUpdate(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class Topic(TopicCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class SourceCreate(Contract):
    name: str = Field(min_length=1, max_length=120)
    feed_url: HttpUrl | None = None
    website_url: HttpUrl
    is_active: bool = False

    @model_validator(mode="after")
    def valid_feed(self):
        if self.is_active and not self.feed_url:
            raise ValueError("An active source requires a feed URL")
        return self


class SourceUpdate(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    feed_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    is_active: bool | None = None


class Source(SourceCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class TopicMatch(Contract):
    topic: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ClassificationResult(Contract):
    target_topics: list[TopicMatch] = Field(max_length=3)
    non_target_topics: list[TopicMatch] = Field(max_length=3)


class ContentResult(Contract):
    title: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)


class GenerationCreate(Contract):
    article_ids: list[str] = Field(min_length=1, max_length=50)
    outputs: list[Literal["BLOG", "LINKEDIN"]] = Field(min_length=1, max_length=2)
    force_refresh_sources: bool = False

    @model_validator(mode="after")
    def unique_selection(self):
        if len(set(self.article_ids)) != len(self.article_ids) or len(set(self.outputs)) != len(self.outputs):
            raise ValueError("Selections must be unique")
        return self


class Regenerate(Contract):
    additional_instructions: str = Field(default="", max_length=8000)
    depends_on_version_id: str | None = None


class Accepted(Contract):
    id: str
    status: Literal["PENDING"] = "PENDING"


class Version(Contract):
    operation_id: str | None = None
    id: str
    generation_output_id: str
    version: int
    title: str
    content_markdown: str
    additional_instructions: str
    model_used: str
    prompt_version: str
    prompt_hash: str
    status: Literal["DRAFT", "APPROVED", "ARCHIVED"]
    created_at: datetime
    approved_at: datetime | None


class Article(Contract):
    id: str
    source_id: str
    title: str
    url: str
    normalized_url: str
    rss_guid: str | None
    published_at: datetime | None
    discovered_at: datetime
    created_at: datetime
    updated_at: datetime


class Run(Contract):
    id: str
    trigger_type: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]
    schedule_slot: str | None
    threshold: float
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    sources_count: int
    entries_found: int
    known_articles: int
    new_articles: int
    classified_count: int
    failed_count: int
    target_count: int
    non_target_count: int


class Generation(Contract):
    id: str
    status: Literal[
        "PENDING",
        "CRAWLING",
        "PREPARING_CONTEXT",
        "GENERATING",
        "COMPLETED",
        "COMPLETED_WITH_ERRORS",
        "FAILED",
    ]
    generate_blog: bool
    generate_linkedin: bool
    force_refresh_sources: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DiscoverySettings(Contract):
    enabled: bool = False
    frequency: Literal["DAILY", "WEEKLY"] = "WEEKLY"
    day_of_week: int = Field(default=0, ge=0, le=6)
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    timezone: str = "Europe/Rome"

    @model_validator(mode="after")
    def valid_timezone(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown timezone") from None
        return self


class RuntimeSettings(Contract):
    openrouter_auto_resume: bool = True
    openrouter_requests_per_minute: int = Field(default=20, ge=1, le=10000)
    openrouter_requests_per_day: int = Field(default=50, ge=1, le=1000000)
    email_enabled: bool = False
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    classification_threshold: float = Field(default=0.7, ge=0, le=1)
    crawl_cache_days: int = Field(default=30, ge=0, le=365)


class ModelCreate(Contract):
    model: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0)
    enabled: bool = True


class Model(ModelCreate):
    id: str


class Summary(Contract):
    articles: int
    sources: int
    active_topics: int
    generations: int
    drafts: int
    mode: Literal["live"] = "live"


class Items(Contract, Generic[T]):
    items: list[T]


class GenerationSource(Contract):
    id: str
    generation_run_id: str
    article_id: str
    original_url: str
    article_title: str
    crawl_status: Literal["PENDING", "CRAWLING", "SUCCESS", "FAILED"]
    selected_at: datetime


class GenerationOutput(Contract):
    id: str
    generation_run_id: str
    output_type: Literal["BLOG", "LINKEDIN"]
    created_at: datetime


class EmailDelivery(Contract):
    content_html: str | None = None
    sender: str | None = None
    attempted_at: datetime | None = None
    id: str
    classification_run_id: str
    provider: str
    recipient: str
    subject: str
    status: Literal["PENDING", "SENT", "FAILED"]
    provider_message_id: str | None
    sent_at: datetime | None
    error_code: str | None
    created_at: datetime


class DiscoverySettingsUpdate(Contract):
    enabled: bool | None = None
    frequency: Literal["DAILY", "WEEKLY"] | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    timezone: str | None = None


class RuntimeSettingsUpdate(Contract):
    openrouter_auto_resume: bool | None = None
    openrouter_requests_per_minute: int | None = Field(default=None, ge=1, le=10000)
    openrouter_requests_per_day: int | None = Field(default=None, ge=1, le=1000000)
    email_enabled: bool | None = None
    discovery: DiscoverySettingsUpdate | None = None
    classification_threshold: float | None = Field(default=None, ge=0, le=1)
    crawl_cache_days: int | None = Field(default=None, ge=0, le=365)


class ModelUpdate(Contract):
    model: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0)
    enabled: bool | None = None


class FeedTest(Contract):
    feed_url: HttpUrl


class ArticleView(Article):
    source_name: str
    classification: dict | None = None


class RunDetail(Run):
    topics: list[dict]
    articles: list[ArticleView]
    events: list[dict]
    emails: list[EmailDelivery]


class GenerationDetail(Generation):
    sources: list[dict]
    outputs: list[dict]
    events: list[dict]
    jobs: list[dict]


class ModelOrder(Contract):
    ids: list[str] = Field(min_length=1, max_length=100)
