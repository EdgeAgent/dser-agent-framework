"""Resolve a stale preference against current account evidence with DSER."""

from datetime import UTC, datetime, timedelta

from dser import (
    ActionResult,
    AgentTask,
    Claim,
    DSERAgent,
    InMemoryStore,
    MappingVerifier,
    MemoryRecord,
    ReconciliationPolicy,
    RiskLevel,
    SourceKind,
)

memory = InMemoryStore()
memory.write(
    MemoryRecord(
        claim=Claim(
            key="customer.delivery_preference",
            value="email",
            source=SourceKind.MEMORY,
            authority=0.30,
            confidence=0.80,
            relevance=0.95,
            provenance="episode:preference-archive",
            support=("old consent record",),
            observed_at=datetime.now(UTC) - timedelta(days=90),
        ),
        task_goal="Remember delivery preference",
        outcome="Historical preference imported.",
        validated=True,
        useful=True,
    )
)

current = Claim(
    key="customer.delivery_preference",
    value="sms",
    source=SourceKind.SYSTEM_OF_RECORD,
    authority=0.95,
    confidence=0.99,
    relevance=1.0,
    provenance="crm-api:customer-42",
    support=("updated consent timestamp",),
)
verified = Claim(
    key="customer.delivery_preference",
    value="sms",
    source=SourceKind.VERIFICATION,
    authority=1.0,
    confidence=1.0,
    relevance=1.0,
    provenance="crm-api:verification-42",
    support=("verification request id",),
)

agent = DSERAgent(
    memory=memory,
    policy=ReconciliationPolicy(),
    verifier=MappingVerifier({"customer.delivery_preference": verified}),
)
result = agent.decide(
    AgentTask(
        key="customer.delivery_preference",
        goal="Select the channel for a delivery notification.",
        risk=RiskLevel.MEDIUM,
        permissions=frozenset({"send_notification"}),
    ),
    observations=(current,),
    execute=lambda _task, claim: ActionResult(
        success=True,
        message=f"Notification queued for {claim.value}.",
    ),
)

print(result.decision.disposition.value)
print(result.decision.reason)
print(result.action.message if result.action else "No action executed")
