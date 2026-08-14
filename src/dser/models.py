"""Typed domain objects for Dual-Stream Evidence Reconciliation (DSER)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4


class SourceKind(str, Enum):
    """Origin categories used when evaluating evidence authority."""

    SYSTEM_OF_RECORD = "system_of_record"
    VERIFICATION = "verification"
    TOOL = "tool"
    USER = "user"
    DOCUMENT = "document"
    MEMORY = "memory"
    MODEL = "model"


class RiskLevel(str, Enum):
    """Expected harm if an agent acts on an incorrect conclusion."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def requires_verification_on_conflict(self) -> bool:
        return self in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}


class Disposition(str, Enum):
    """The only decisions a DSER reconciliation policy may emit."""

    ACT = "act"
    PLAN = "plan"
    VERIFY = "verify"
    ASK = "ask"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class Claim:
    """A normalized proposition with source and quality metadata.

    ``key`` identifies the decision variable (for example, ``account.plan``),
    while ``value`` is the asserted value. A claim is intentionally independent
    of raw document format so observations and memories can be compared fairly.
    """

    key: str
    value: str
    source: SourceKind
    authority: float
    confidence: float
    relevance: float
    provenance: str | None = None
    support: tuple[str, ...] = ()
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    identifier: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        for field_name in ("authority", "confidence", "relevance"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0.0 and 1.0")
        if not self.key.strip():
            raise ValueError("key must not be empty")
        if not self.value.strip():
            raise ValueError("value must not be empty")

    @property
    def has_provenance(self) -> bool:
        return bool(self.provenance or self.support)

    def freshness(self, now: datetime | None = None, horizon: timedelta = timedelta(days=30)) -> float:
        """Return a bounded freshness score based on age and optional expiry."""

        now = now or datetime.now(UTC)
        observed_at = self.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        if self.expires_at is not None:
            expires_at = self.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if now >= expires_at:
                return 0.0
        age = max(timedelta(0), now - observed_at)
        return max(0.0, 1.0 - (age / horizon))


@dataclass(frozen=True, slots=True)
class AgentTask:
    """A bounded decision request for a single DSER reconciliation cycle."""

    key: str
    goal: str
    risk: RiskLevel = RiskLevel.LOW
    permissions: frozenset[str] = frozenset()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("task key must not be empty")
        if not self.goal.strip():
            raise ValueError("task goal must not be empty")


@dataclass(frozen=True, slots=True)
class Decision:
    """Auditable output from the reconciliation policy."""

    disposition: Disposition
    reason: str
    selected_claim: Claim | None
    score: float
    conflicts: tuple[Claim, ...] = ()
    required_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Result of an optional typed action after a decision has been made."""

    success: bool
    message: str
    output: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """An episodic record eligible for selective long-term retention."""

    claim: Claim
    task_goal: str
    outcome: str
    validated: bool
    useful: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def eligible_for_retention(self) -> bool:
        return self.validated and self.useful and self.claim.has_provenance


@dataclass(frozen=True, slots=True)
class AgentResult:
    """End-to-end DSER run output suitable for logs, tests, and UIs."""

    task: AgentTask
    decision: Decision
    claims: tuple[Claim, ...]
    action: ActionResult | None
    verification_used: bool
    memory_written: bool
