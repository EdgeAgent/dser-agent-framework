from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from dser import (
    ActionResult,
    AgentTask,
    Claim,
    DSERAgent,
    Disposition,
    InMemoryStore,
    MappingVerifier,
    MemoryRecord,
    ReconciliationPolicy,
    RiskLevel,
    SourceKind,
)


def claim(
    *,
    key: str = "account.plan",
    value: str = "monthly",
    source: SourceKind = SourceKind.SYSTEM_OF_RECORD,
    authority: float = 0.9,
    provenance: str | None = "record:1",
    observed_at: datetime | None = None,
) -> Claim:
    return Claim(
        key=key,
        value=value,
        source=source,
        authority=authority,
        confidence=0.95,
        relevance=1.0,
        provenance=provenance,
        support=("support:1",) if provenance else (),
        observed_at=observed_at or datetime.now(UTC),
    )


class DSERAgentTests(unittest.TestCase):
    def test_medium_risk_conflict_is_verified_and_current_value_wins(self) -> None:
        memory = InMemoryStore()
        stale = claim(
            value="annual",
            source=SourceKind.MEMORY,
            authority=0.35,
            provenance="episode:old",
            observed_at=datetime.now(UTC) - timedelta(days=90),
        )
        memory.write(
            MemoryRecord(
                claim=stale,
                task_goal="remember plan",
                outcome="old snapshot",
                validated=True,
                useful=True,
            )
        )
        current = claim(value="monthly", source=SourceKind.SYSTEM_OF_RECORD, authority=0.95)
        verified = claim(value="monthly", source=SourceKind.VERIFICATION, authority=1.0, provenance="verify:1")
        agent = DSERAgent(
            memory=memory,
            policy=ReconciliationPolicy(),
            verifier=MappingVerifier({"account.plan": verified}),
        )
        task = AgentTask("account.plan", "Select billing plan", RiskLevel.MEDIUM)

        result = agent.decide(
            task,
            observations=(current,),
            execute=lambda _, selected: ActionResult(True, f"used {selected.value}"),
        )

        self.assertEqual(result.decision.disposition, Disposition.ACT)
        self.assertEqual(result.decision.selected_claim, verified)
        self.assertTrue(result.verification_used)
        self.assertTrue(result.memory_written)
        self.assertEqual(result.action.message, "used monthly")

    def test_low_risk_conflict_can_route_to_plan_when_evidence_is_decisive(self) -> None:
        memory = InMemoryStore()
        memory.write(
            MemoryRecord(
                claim=claim(value="annual", source=SourceKind.MEMORY, authority=0.20, provenance="episode:old"),
                task_goal="remember plan",
                outcome="old snapshot",
                validated=True,
                useful=True,
            )
        )
        agent = DSERAgent(memory=memory, policy=ReconciliationPolicy())

        result = agent.decide(
            AgentTask("account.plan", "Prepare a non-consequential draft", RiskLevel.LOW),
            observations=(claim(value="monthly", authority=1.0),),
        )

        self.assertEqual(result.decision.disposition, Disposition.PLAN)
        self.assertFalse(result.verification_used)

    def test_missing_evidence_defers(self) -> None:
        agent = DSERAgent(memory=InMemoryStore(), policy=ReconciliationPolicy())
        result = agent.decide(
            AgentTask("shipment.status", "Report shipment status", RiskLevel.LOW),
            observations=(),
        )

        self.assertEqual(result.decision.disposition, Disposition.DEFER)
        self.assertIsNone(result.decision.selected_claim)

    def test_medium_risk_claim_without_provenance_asks_for_support(self) -> None:
        agent = DSERAgent(memory=InMemoryStore(), policy=ReconciliationPolicy())
        result = agent.decide(
            AgentTask("address", "Use address for delivery", RiskLevel.MEDIUM),
            observations=(claim(key="address", value="1 Main Street", provenance=None),),
        )

        self.assertEqual(result.decision.disposition, Disposition.ASK)
        self.assertFalse(result.memory_written)

    def test_memory_rejects_unvalidated_records(self) -> None:
        memory = InMemoryStore()
        stored = memory.write(
            MemoryRecord(
                claim=claim(),
                task_goal="test",
                outcome="unverified",
                validated=False,
                useful=True,
            )
        )

        self.assertFalse(stored)
        self.assertEqual(memory.records(), ())


if __name__ == "__main__":
    unittest.main()
