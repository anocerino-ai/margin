"""Fair selection from ordered per-source candidate lists."""

from collections import deque


def balanced_entries(candidates, limit):
    """Yield one entry per nonempty source per round, redistributing unused slots."""
    active = deque((source, iter(entries)) for source, entries in candidates)
    selected = 0
    while active and selected < limit:
        source, entries = active.popleft()
        try:
            entry = next(entries)
        except StopIteration:
            continue
        yield source, entry
        selected += 1
        active.append((source, entries))
