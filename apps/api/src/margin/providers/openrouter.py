"""Bounded fallback with persisted circular cursor and per-attempt audit."""

import logging

import httpx
from pydantic import ValidationError

from margin.repositories.core import identifier, now


class ModelsExhausted(RuntimeError):
    pass


class OpenRouterProvider:
    def __init__(self, db, token: str, client=None, max_output_tokens=5000):
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
        for offset in range(len(models)):
            model = models[(start + offset) % len(models)]["model"]
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
                    previous + offset + 1,
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
                    previous + offset + 1,
                    model,
                    error,
                )
            if result is not None:
                return result
        raise ModelsExhausted("ALL_MODELS_FAILED")
