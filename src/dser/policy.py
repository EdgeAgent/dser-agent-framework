"""Provenance-aware reconciliation policy for DSER."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ledger import EvidenceLedger
from .models import AgentTask, Claim, Decision, Disposition, SourceKind


@dataclass(frozen=True, slots=True)
class PolicyWeights:
    """Configurable weights for non-safety-critical evidence ranking."""

    authority: float = 0.30
    freshness: float = 0.22
    provenance: float = 0.18
    confidence: float = 0.15
    relevance: float = 0.15

    def __post_init__(self) -> None:
        total = sum((self.authority, self.freshness, self.provenance, self.confidence, self.relevance))
        if not 0.999 <= total <= 1.001:
            raise ValueError("policy weights must sum to 1.0")


@dataclass(frozen=True, slots=True)
class ReconciliationPolicy:
    """Selects a safe disposition from ledger evidence and task risk.

    Scores help rank supported claims. They do not override hard policy rules:
    missing provenance and material conflict must be surfaced, particularly for
    medium- and high-risk tasks.
    """

    weights: PolicyWeights = PolicyWeights()
    minimum_action_score: float = 0.55
    decisive_margin: float = 0.12

    def score(self, claim: Claim, now: datetime | None = None) -> float:
        provenance = 1.0 if claim.has_provenance else 0.0
        return (
            self.weights.authority * claim.authority
            + self.weights.freshness * claim.freshness(now)
            + self.weights.provenance * provenance
            + self.weights.confidence * claim.confidence
            + self.weights.relevance * claim.relevance
        )

    def reconcile(self, task: AgentTask, ledger: EvidenceLedger, now: datetime | None = None) -> Decision:
        claims = ledger.for_key(task.key)
        if not claims:
            return Decision(
                disposition=Disposition.DEFER,
                reason="No current observation or retrievable memory supports the requested decision.",
                selected_claim=None,
                score=0.0,
                required_evidence=(f"Evidence for {task.key}",),
            )

        ranked = sorted(claims, key=lambda claim: self.score(claim, now), reverse=True)
        selected = ranked[0]
        selected_score = self.score(selected, now)
        conflicts = ledger.conflicts_for(task.key)

        if conflicts:
            verified_claim = next(
                (
                    claim
                    for claim in ranked
                    if claim.source is SourceKind.VERIFICATION and claim.has_provenance
                ),
                None,
            )
            if verified_claim is not None:
                return Decision(
                    disposition=Disposition.ACT,
                    reason="An authoritative verification record resolved the material conflict.",
                    selected_claim=verified_claim,
                    score=self.score(verified_claim, now),
                    conflicts=conflicts,
                )

            runner_up = ranked[1] if len(ranked) > 1 else None
            margin = selected_score - self.score(runner_up, now) if runner_up else selected_score
            needs_verification = task.risk.requires_verification_on_conflict or (
                margin < self.decisive_margin or not selected.has_provenance
            )
            if needs_verification:
                return Decision(
                    disposition=Disposition.VERIFY,
                    reason="Material claims disagree; verification is required before a risk-aware action.",
                    selected_claim=selected,
                    score=selected_score,
                    conflicts=conflicts,
                    required_evidence=(f"Authoritative confirmation for {task.key}",),
                )
            return Decision(
                disposition=Disposition.PLAN,
                reason="Claims disagree, but a low-risk action plan can use the most authoritative current evidence.",
                selected_claim=selected,
                score=selected_score,
                conflicts=conflicts,
            )

        if not selected.has_provenance and task.risk.requires_verification_on_conflict:
            return Decision(
                disposition=Disposition.ASK,
                reason="Evidence has no attributable provenance for a consequential decision.",
                selected_claim=selected,
                score=selected_score,
                required_evidence=("A source record or user confirmation",),
            )

        if selected_score < self.minimum_action_score:
            return Decision(
                disposition=Disposition.ASK,
                reason="Evidence is insufficiently fresh, relevant, or supported to act safely.",
                selected_claim=selected,
                score=selected_score,
                required_evidence=(f"Higher-quality evidence for {task.key}",),
            )

        return Decision(
            disposition=Disposition.ACT,
            reason="Available evidence agrees and satisfies the configured action threshold.",
            selected_claim=selected,
            score=selected_score,
        )
