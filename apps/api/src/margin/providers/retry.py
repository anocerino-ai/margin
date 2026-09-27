"""Configurable sequential retry delays, independent of transport and persistence."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


@dataclass(frozen=True)
class RetryPolicy:
    attempts_per_model: int = 2
    initial_delay: float = 45
    max_delay: float = 180

    def delay(self, failed_attempt, retry_after=None):
        delay = min(self.max_delay, self.initial_delay * 2 ** (failed_attempt - 1))
        if retry_after:
            try:
                seconds = float(retry_after)
            except ValueError:
                try:
                    seconds = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    seconds = 0
            if math.isfinite(seconds):
                delay = max(delay, seconds)
        return delay
