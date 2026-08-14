"""Run a self-contained DSER demonstration with ``python -m dser``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from json import dumps

from .agent import DSERAgent
from .memory import InMemoryStore
from .models import ActionResult, AgentTask, Claim, RiskLevel, SourceKind
from .policy import ReconciliationPolicy
from .tools import MappingVerifier


def main() -> None:
    old_claim = Claim(
        key="account.plan",
        value="annual",
        source=SourceKind.MEMORY,
        authority=0.35,
        confidence=0.75,
        relevance=0.9,
        provenance="episode:billing-2025-11",
        support=("prior verified account snapshot",),
        observed_at=datetime.now(UTC) - timedelta(days=45),
    )
    current_claim = Claim(
        key="account.plan",
        value="monthly",
        source=SourceKind.SYSTEM_OF_RECORD,
        authority=0.95,
        confidence=0.98,
        relevance=1.0,
        provenance="billing-api:v2",
        support=("account-id:acct_001",),
    )
    verified_claim = Claim(
        key="account.plan",
        value="monthly",
        source=SourceKind.VERIFICATION,
        authority=1.0,
        confidence=1.0,
        relevance=1.0,
        provenance="billing-api:verification",
        support=("verification-id:ver_001",),
    )

    memory = InMemoryStore()
    from .models import MemoryRecord

    memory.write(
        MemoryRecord(
            claim=old_claim,
            task_goal="Maintain account plan context",
            outcome="Prior snapshot validated.",
            validated=True,
            useful=True,
        )
    )
    agent = DSERAgent(
        memory=memory,
        policy=ReconciliationPolicy(),
        verifier=MappingVerifier({"account.plan": verified_claim}),
    )
    task = AgentTask(
        key="account.plan",
        goal="Select the account plan to display before updating the billing summary.",
        risk=RiskLevel.MEDIUM,
        permissions=frozenset({"display_billing_summary"}),
    )
    result = agent.decide(
        task,
        observations=(current_claim,),
        execute=lambda _task, claim: ActionResult(
            success=True,
            message=f"Displayed billing summary for {claim.value} plan.",
        ),
    )
    print(
        dumps(
            {
                "disposition": result.decision.disposition.value,
                "selected_value": result.decision.selected_claim.value if result.decision.selected_claim else None,
                "reason": result.decision.reason,
                "verification_used": result.verification_used,
                "memory_written": result.memory_written,
                "action": result.action.message if result.action else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
