from typing import Protocol

from pydantic import BaseModel


class LLMProvider(Protocol):
    def generate(
        self, prompt: str, context: str, schema: type[BaseModel], operation_id: str, operation_type: str
    ) -> BaseModel: ...


class CrawlProvider(Protocol):
    """Only GenerationService may depend on this port."""

    def crawl(self, url: str) -> str: ...


class EmailProvider(Protocol):
    def send(self, recipient: str, subject: str, html: str, idempotency_key: str) -> str: ...


class JobDispatcher(Protocol):
    def enqueue_statement(self, kind: str, resource_id: str) -> tuple[str, list]: ...
