"""Bounded fallback with persisted circular cursor and per-attempt audit."""

import logging
import time

import httpx
from pydantic import ValidationError

from margin.providers.quota import QuotaDeferred, pause_until
from margin.providers.retry import RetryPolicy
from margin.repositories.core import identifier, now


class ModelsExhausted(RuntimeError):
    pass


class OpenRouterProvider:
    def __init__(
        self,
        db,
        token: str,
        client=None,
        max_output_tokens=5000,
        retry_policy=None,
        quota=None,
        sleep=time.sleep,
        clock=time.time,
    ):
        self.quota = quota
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleep, self.clock = sleep, clock
        self.db = db
        self.token = token
        self.max_output_tokens = max_output_tokens
        self.client = client or httpx.Client(timeout=45)

    def generate(self, prompt, context, schema, operation_id, operation_type, validate=None):
        models = self.db.query("SELECT model FROM llm_models WHERE enabled=1 ORDER BY position")
        if not models:
            raise ModelsExhausted("NO_ENABLED_MODELS")
        # Atomic persistent allocation. Cursor advances even if all models fail.
        cursor = self.db.query(
            "INSERT INTO app_settings(key,value,updated_at) VALUES ('llm.cursor','1',?) ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at RETURNING value",
            [now()],
        )[0]
        start = (int(cursor["value"]) - 1) % len(models)
        previous = self.db.query(
            "SELECT COALESCE(MAX(attempt_number),0) n FROM llm_attempts WHERE operation_type=? AND operation_id=?",
            [operation_type, operation_id],
        )[0]["n"]
        attempt_number = previous
        next_attempt_at = 0
        for offset in range(len(models)):
            model = models[(start + offset) % len(models)]["model"]
            used = self.db.query(
                "SELECT COUNT(*) n FROM llm_attempts WHERE operation_type=? AND operation_id=? AND model=? AND COALESCE(error_code,'')!='PROVIDER_DAILY_QUOTA_EXHAUSTED'",
                [operation_type, operation_id, model],
            )[0]["n"]
            for model_attempt in range(used + 1, self.retry_policy.attempts_per_model + 1):
                cooldown = self.db.query("SELECT value FROM app_settings WHERE key='llm.cooldown_until'")
                deadline = max(next_attempt_at, float(cooldown[0]["value"]) if cooldown else 0)
                while deadline > self.clock():
                    self.sleep(min(20, deadline - self.clock()))
                    # FencedDatabase verifies lease ownership before another provider call.
                    self.db.query("SELECT 1")
                if self.quota:
                    self.quota.reserve()
                attempt_number += 1
                retry_after = None
                started = now()
                status, error, result = "SUCCESS", None, None
                try:
                    response = self.client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "model": model,
                            "max_tokens": min(self.max_output_tokens, 1000)
                            if operation_type == "CLASSIFICATION"
                            else self.max_output_tokens,
                            "messages": [
                                {"role": "system", "content": prompt},
                                {"role": "user", "content": context},
                            ],
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": schema.__name__,
                                    "strict": True,
                                    "schema": schema.model_json_schema(),
                                },
                            },
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    choice = body["choices"][0]
                    if choice.get("finish_reason") == "length":
                        raise ValueError("OUTPUT_TRUNCATED")
                    if choice.get("finish_reason") == "content_filter":
                        raise ValueError("CONTENT_FILTERED")
                    content = choice["message"]["content"]
                    if not content:
                        raise ValueError("EMPTY_OUTPUT")
                    result = schema.model_validate_json(content)
                    if validate:
                        validate(result)
                except httpx.TimeoutException:
                    status, error = "TIMEOUT", "PROVIDER_TIMEOUT"
                except httpx.HTTPStatusError as exc:
                    status, error = "HTTP_ERROR", f"PROVIDER_HTTP_{exc.response.status_code}"
                    retry_after = exc.response.headers.get("Retry-After")
                    try:
                        message = str(exc.response.json().get("error", {}).get("message", ""))
                    except (ValueError, AttributeError):
                        message = ""
                    if exc.response.status_code == 429 and "free-models-per-day" in message:
                        error = "PROVIDER_DAILY_QUOTA_EXHAUSTED"
                except httpx.HTTPError:
                    status, error = "HTTP_ERROR", "PROVIDER_NETWORK_ERROR"
                except ValidationError as exc:
                    # Only schema error categories are retained; never output values or provider bodies.
                    kinds = sorted({e["type"] for e in exc.errors(include_input=False, include_url=False)})
                    status, error, result = (
                        "INVALID_OUTPUT",
                        "SCHEMA_VALIDATION_FAILED:" + ",".join(kinds)[:160],
                        None,
                    )
                except ValueError as exc:
                    safe_codes = {
                        "OUTPUT_TRUNCATED",
                        "CONTENT_FILTERED",
                        "EMPTY_OUTPUT",
                        "TOPIC_SNAPSHOT_MISMATCH",
                    }
                    error = str(exc) if str(exc) in safe_codes else "INVALID_RESPONSE_JSON"
                    status, result = "INVALID_OUTPUT", None
                except (KeyError, IndexError, TypeError):
                    status, error, result = "INVALID_OUTPUT", "INVALID_RESPONSE_STRUCTURE", None
                self.db.query(
                    "INSERT INTO llm_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [
                        identifier(),
                        operation_type,
                        operation_id,
                        "openrouter",
                        model,
                        attempt_number,
                        status,
                        started,
                        now(),
                        error,
                    ],
                )
                if error:
                    logging.getLogger(__name__).warning(
                        "LLM attempt failed operation=%s type=%s attempt=%s model=%s code=%s",
                        operation_id,
                        operation_type,
                        attempt_number,
                        model,
                        error,
                    )
                if error == "PROVIDER_DAILY_QUOTA_EXHAUSTED" and self.quota:
                    deadline = max(
                        self.quota.next_day(), self.clock() + self.retry_policy.delay(1, retry_after)
                    )
                    pause_until(self.db, deadline, error)
                    raise QuotaDeferred(error)
                if result is not None:
                    return result
                delay = self.retry_policy.delay(model_attempt, retry_after)
                next_attempt_at = self.clock() + delay
                if error == "PROVIDER_HTTP_429":
                    self.db.query(
                        "INSERT INTO app_settings(key,value,updated_at) VALUES ('llm.cooldown_until',?,?) ON CONFLICT(key) DO UPDATE SET value=CAST(MAX(CAST(value AS REAL),CAST(excluded.value AS REAL)) AS TEXT),updated_at=excluded.updated_at",
                        [str(next_attempt_at), now()],
                    )
                logging.getLogger(__name__).warning(
                    "LLM backoff operation=%s model=%s model_attempt=%s delay_seconds=%s",
                    operation_id,
                    model,
                    model_attempt,
                    delay,
                )
        raise ModelsExhausted("ALL_MODELS_FAILED")
