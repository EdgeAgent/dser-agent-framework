"""The smallest runnable DSER decision cycle."""

from dser import (
    ActionResult,
    AgentTask,
    Claim,
    DSERAgent,
    InMemoryStore,
    ReconciliationPolicy,
    RiskLevel,
    SourceKind,
)


agent = DSERAgent(memory=InMemoryStore(), policy=ReconciliationPolicy())

current_status = Claim(
    key="order.status",
    value="shipped",
    source=SourceKind.SYSTEM_OF_RECORD,
    authority=0.95,
    confidence=0.99,
    relevance=1.0,
    provenance="orders-api:v1",
    support=("order:123",),
)

task = AgentTask(
    key="order.status",
    goal="Tell the customer the latest order status.",
    risk=RiskLevel.LOW,
    permissions=frozenset({"send_customer_update"}),
)

result = agent.decide(
    task,
    observations=(current_status,),
    execute=lambda _task, claim: ActionResult(
        success=True,
        message=f"Customer update prepared: order is {claim.value}.",
    ),
)

print(result.decision.disposition.value)
print(result.decision.reason)
print(result.action.message if result.action else "No action executed")
