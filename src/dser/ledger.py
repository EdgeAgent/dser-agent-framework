"""Evidence ledger and deterministic conflict analysis for DSER."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .models import Claim


@dataclass(slots=True)
class EvidenceLedger:
    """Stores normalized claims without collapsing their source metadata."""

    _claims: list[Claim] = field(default_factory=list)

    def add(self, claim: Claim) -> None:
        """Append a claim unless the same source record is already present."""

        if any(existing.identifier == claim.identifier for existing in self._claims):
            return
        self._claims.append(claim)

    def extend(self, claims: Iterable[Claim]) -> None:
        for claim in claims:
            self.add(claim)

    def for_key(self, key: str) -> tuple[Claim, ...]:
        return tuple(claim for claim in self._claims if claim.key == key)

    def all(self) -> tuple[Claim, ...]:
        return tuple(self._claims)

    def values_for(self, key: str) -> set[str]:
        return {claim.value for claim in self.for_key(key)}

    def conflicts_for(self, key: str) -> tuple[Claim, ...]:
        """Return material claims only when more than one value is asserted."""

        claims = self.for_key(key)
        return claims if len({claim.value for claim in claims}) > 1 else ()

    def grouped(self) -> dict[str, tuple[Claim, ...]]:
        groups: dict[str, list[Claim]] = defaultdict(list)
        for claim in self._claims:
            groups[claim.key].append(claim)
        return {key: tuple(items) for key, items in groups.items()}
