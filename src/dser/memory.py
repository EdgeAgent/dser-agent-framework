"""Selective episodic memory for DSER agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Claim, MemoryRecord


@dataclass(slots=True)
class InMemoryStore:
    """Small reference memory store with an explicit retention policy.

    The store is intentionally deterministic and in-process. Production users can
    implement the same ``retrieve`` and ``write`` methods for a vector database,
    document system, or durable event store.
    """

    _records: list[MemoryRecord] = field(default_factory=list)

    def retrieve(self, key: str, limit: int = 8) -> tuple[Claim, ...]:
        """Return newest matching claims first, bounded to avoid context flooding."""

        matching = [record.claim for record in self._records if record.claim.key == key]
        matching.sort(key=lambda claim: claim.observed_at, reverse=True)
        return tuple(matching[:limit])

    def write(self, record: MemoryRecord) -> bool:
        """Persist only validated, useful, source-attributed outcomes."""

        if not record.eligible_for_retention:
            return False
        self._records.append(record)
        return True

    def records(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)
