"""Verification interfaces for DSER conflict resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import AgentTask, Claim


class VerificationTool(Protocol):
    """Adapter contract for a trusted source of record or verification service."""

    def verify(self, task: AgentTask) -> Claim | None:
        """Return authoritative evidence for the task key, or ``None`` if unavailable."""


@dataclass(slots=True)
class MappingVerifier:
    """Deterministic verifier for examples, tests, and local prototyping."""

    responses: dict[str, Claim] = field(default_factory=dict)

    def verify(self, task: AgentTask) -> Claim | None:
        return self.responses.get(task.key)
