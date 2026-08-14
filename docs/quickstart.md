# DSER Quickstart

This tutorial takes you from a clean environment to a complete **Dual-Stream Evidence Reconciliation** decision. By the end, a DSER agent will receive a current system record, evaluate its confidence and provenance, decide that action is permitted, perform a typed callback, and selectively retain the validated outcome.

> **What DSER does:** It controls a single decision boundary. It does not replace your LLM, workflow engine, database, or authorization system. DSER decides whether the evidence available for one task supports an action, needs verification, requires a question, or is insufficient.

## 1. Install the package

DSER requires Python 3.11 or later. Its optional public HTTP retrieval adapter installs `requests`; no model, database, or hosted service is required.

```bash
git clone https://github.com/EdgeAgent/dser-agent-framework.git
cd dser-agent-framework
python3 -m pip install -e .
```

Confirm the bundled demonstration works:

```bash
python3 -m dser
```

The output should show a verified `monthly` account-plan decision. The full source is in [`src/dser/__main__.py`](../src/dser/__main__.py).

## 2. Run the smallest decision cycle

The following example is available as [`examples/quickstart.py`](../examples/quickstart.py):

```bash
python3 examples/quickstart.py
```

It creates a fresh claim from an order system, then asks DSER whether it can tell the customer the status.

```python
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
```

The expected disposition is `act`. The system record is fresh, source-attributed, highly authoritative, relevant to the task, and has no conflicting value in memory.

## 3. Understand the two inputs

Each call to `agent.decide()` combines two separate streams:

| Stream | You provide it through | Typical source | DSER treatment |
| --- | --- | --- | --- |
| **Current observation** | `observations=(...)` or an observation-provider function | User input, API response, sensor, tool result, system of record | Fresh evidence for the decision now. |
| **Retrieved memory** | `memory.retrieve(task.key)` | Prior validated episode, preference, document-derived fact | Context that DSER evaluates but does not blindly trust. |

The agent runs observation acquisition and memory retrieval concurrently, then puts both into an `EvidenceLedger`. Claims retain their own source and timestamp so a memory record cannot silently become a current system record.

## 4. Create claims deliberately

A `Claim` is the core DSER data unit. `key` identifies the variable being decided, while `value` is the asserted answer. All score-like fields must be between `0.0` and `1.0`.

| Field | Required | Practical guidance |
| --- | --- | --- |
| `key` | Yes | Use a stable decision variable such as `customer.delivery_preference` or `invoice.status`. |
| `value` | Yes | Use a canonical representation so equivalent values compare reliably. |
| `source` | Yes | Select the origin category that best describes the evidence. |
| `authority` | Yes | Reflect how much the source should influence this **specific** task. |
| `confidence` | Yes | Express the reliability of this individual assertion, not the agent’s enthusiasm. |
| `relevance` | Yes | Express how directly the assertion addresses the task key. |
| `provenance` | Recommended | Store a source URI, record identifier, request identifier, or document locator. |
| `support` | Recommended | Preserve short, inspectable evidence references such as record IDs or text spans. |
| `observed_at` | Optional | Defaults to the current UTC time; set it explicitly for imported or retrieved data. |
| `expires_at` | Optional | Set a hard expiry for short-lived permissions, balances, prices, or status data. |

Use `SourceKind.SYSTEM_OF_RECORD` for the source that is authoritative for the variable, `SourceKind.MEMORY` for past validated episodes, and `SourceKind.VERIFICATION` only for a response obtained specifically to resolve the current task.

## 5. Give the task an honest risk level

`AgentTask` provides the context needed to interpret the evidence. `key` must match the claims DSER should reconcile.

```python
task = AgentTask(
    key="customer.delivery_preference",
    goal="Choose the notification channel for a delivery update.",
    risk=RiskLevel.MEDIUM,
    permissions=frozenset({"send_notification"}),
    metadata={"customer_id": "cust_42"},
)
```

| Risk level | Recommended use | Conflict behavior |
| --- | --- | --- |
| `LOW` | Reversible, low-impact drafts or information display | A decisive conflict may return `plan`; ambiguous evidence still triggers `verify`. |
| `MEDIUM` | Notifications, preference changes, business-state updates | Material conflicts route to `verify`. |
| `HIGH` | Actions with material customer, operational, or compliance impact | Material conflicts route to `verify`; integrate human approval and strong authorization externally. |
| `CRITICAL` | Safety- or mission-critical actions | DSER still routes conflicts to `verify`; your application should add explicit approval and fail-closed controls. |

`permissions` and `metadata` are retained on the task for your application. The v0.1 reference policy does not itself enforce the permission set; the action executor must do that.

## 6. Handle a conflict with a verifier

For a medium-risk decision, DSER does not let a stale memory override current evidence. The executable [`examples/resolve_conflict.py`](../examples/resolve_conflict.py) demonstrates this flow:

```bash
python3 examples/resolve_conflict.py
```

The example provides an old memory that says `email`, a current customer-record claim that says `sms`, and a `MappingVerifier` that confirms `sms`. The final disposition is `act` because the verification response is source-attributed and has resolved the conflict.

```python
from dser import Claim, MappingVerifier, SourceKind

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

verifier = MappingVerifier({"customer.delivery_preference": verified})
```

`MappingVerifier` is intentionally deterministic and is best for local development and tests. For a production verifier, implement the `VerificationTool` protocol:

```python
from dser import AgentTask, Claim, SourceKind

class CustomerRecordVerifier:
    def __init__(self, client):
        self.client = client

    def verify(self, task: AgentTask) -> Claim | None:
        record = self.client.fetch_current_preference(task.metadata["customer_id"])
        if record is None:
            return None
        return Claim(
            key=task.key,
            value=record.channel,
            source=SourceKind.VERIFICATION,
            authority=1.0,
            confidence=1.0,
            relevance=1.0,
            provenance=f"crm:preference:{record.id}",
            support=(record.updated_at.isoformat(),),
            observed_at=record.updated_at,
        )
```

If DSER enters `verify` but no verifier is configured or the verifier returns `None`, `DSERAgent.decide()` returns `ask`. Your application can then request clarification, escalate to a human, or defer the workflow.

## 7. Interpret the result before you do anything else

`DSERAgent.decide()` returns an `AgentResult`, not merely a value. Persist or trace it in your own application when the decision matters.

| `AgentResult` field | Meaning |
| --- | --- |
| `task` | The task that bounded the reconciliation cycle. |
| `decision` | The selected disposition, reason, score, selected claim, conflicts, and required evidence. |
| `claims` | Every claim present in the evidence ledger after any verification response. |
| `action` | The optional `ActionResult` returned by your action callback; `None` when no action ran. |
| `verification_used` | Whether a verifier was configured when the agent entered a verification path. |
| `memory_written` | Whether the resulting validated and useful outcome passed the store’s retention policy. |

Never call a side-effecting tool simply because `selected_claim` is populated. Call it only through the `execute` callback or after checking that `result.decision.disposition is Disposition.ACT`.

## 8. Replace the reference memory store in production

`InMemoryStore` is deterministic, in-process, and deliberately small. Its contract is simple:

```python
class YourMemoryStore:
    def retrieve(self, key: str, limit: int = 8) -> tuple[Claim, ...]:
        ...

    def write(self, record: MemoryRecord) -> bool:
        ...
```

A production adapter may use a vector database to find candidates, but it should return normalized `Claim` objects. It should also preserve DSER’s retention rule: reject records that are not validated, not useful, or not attributable to evidence. The reference store returns matching claims newest first and limits retrieval to eight items by default.

## 9. Tune policy thresholds only with tests

`ReconciliationPolicy` makes its choices using a weighted score across authority, freshness, provenance, confidence, and relevance. The defaults are intentionally visible:

```python
from dser import PolicyWeights, ReconciliationPolicy

policy = ReconciliationPolicy(
    weights=PolicyWeights(
        authority=0.30,
        freshness=0.22,
        provenance=0.18,
        confidence=0.15,
        relevance=0.15,
    ),
    minimum_action_score=0.55,
    decisive_margin=0.12,
)
```

Weights must total `1.0` within a small floating-point tolerance. Scores rank supported claims; they do **not** override the policy’s hard conflict and provenance rules. Add tests for your domain’s known disagreements before changing these thresholds.

## Next steps

Run the [local browser and terminal guide](local-demo.md) to explore DSER interactively, then read the [API reference](api-reference.md) for the full public surface, [design document](design.md) for the architecture contract, and [security policy](../SECURITY.md) before connecting DSER to sensitive tools.
