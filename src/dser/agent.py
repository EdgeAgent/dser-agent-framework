"""End-to-end orchestration for a Dual-Stream Evidence Reconciliation agent."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable

from .ledger import EvidenceLedger
from .memory import InMemoryStore
from .models import (
    ActionResult,
    AgentResult,
    AgentTask,
    Claim,
    Disposition,
    MemoryRecord,
)
from .policy import ReconciliationPolicy
from .tools import VerificationTool

ObservationProvider = Callable[[AgentTask], Iterable[Claim]]
ActionExecutor = Callable[[AgentTask, Claim], ActionResult]


@dataclass(slots=True)
class DSERAgent:
    """A provider-independent orchestrator for evidence-aware agent decisions."""

    memory: InMemoryStore
    policy: ReconciliationPolicy
    verifier: VerificationTool | None = None

    def decide(
        self,
        task: AgentTask,
        observations: Iterable[Claim] | ObservationProvider,
        execute: ActionExecutor | None = None,
    ) -> AgentResult:
        """Run one auditable reconcile-and-act cycle.

        Observation and retrieval work are deliberately concurrent. The resulting
        claims are only combined in an ``EvidenceLedger``, where source metadata
        remains intact for policy evaluation.
        """

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="dser") as pool:
            memory_future = pool.submit(self.memory.retrieve, task.key)
            if callable(observations):
                observation_future = pool.submit(lambda: tuple(observations(task)))
            else:
                observation_future = pool.submit(lambda: tuple(observations))
            retrieved = memory_future.result()
            current = observation_future.result()

        ledger = EvidenceLedger()
        ledger.extend(current)
        ledger.extend(retrieved)
        decision = self.policy.reconcile(task, ledger)
        verification_used = False

        if decision.disposition is Disposition.VERIFY:
            verification_used = self.verifier is not None
            verified = self.verifier.verify(task) if self.verifier else None
            if verified is not None:
                ledger.add(verified)
                decision = self.policy.reconcile(task, ledger)
            else:
                decision = decision.__class__(
                    disposition=Disposition.ASK,
                    reason="Verification was required but no authoritative response was available.",
                    selected_claim=decision.selected_claim,
                    score=decision.score,
                    conflicts=decision.conflicts,
                    required_evidence=decision.required_evidence,
                )

        action: ActionResult | None = None
        if decision.disposition is Disposition.ACT and execute and decision.selected_claim:
            action = execute(task, decision.selected_claim)

        memory_written = False
        if decision.disposition is Disposition.ACT and decision.selected_claim:
            outcome = action.message if action else "Decision accepted without an external action."
            validated = decision.selected_claim.has_provenance
            useful = action.success if action else True
            memory_written = self.memory.write(
                MemoryRecord(
                    claim=decision.selected_claim,
                    task_goal=task.goal,
                    outcome=outcome,
                    validated=validated,
                    useful=useful,
                )
            )

        return AgentResult(
            task=task,
            decision=decision,
            claims=ledger.all(),
            action=action,
            verification_used=verification_used,
            memory_written=memory_written,
        )
