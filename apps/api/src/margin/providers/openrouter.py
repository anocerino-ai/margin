"""Bounded fallback with persisted circular cursor and per-attempt audit."""

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
                result = schema.model_validate_json(response.json()["choices"][0]["message"]["content"])
                if validate:
                    validate(result)
            except httpx.TimeoutException:
                status, error = "TIMEOUT", "PROVIDER_TIMEOUT"
            except httpx.HTTPError:
                status, error = "HTTP_ERROR", "PROVIDER_HTTP_ERROR"
            except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                status, error, result = "INVALID_OUTPUT", "SCHEMA_VALIDATION_FAILED", None
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
            if result is not None:
                return result
        raise ModelsExhausted("ALL_MODELS_FAILED")
