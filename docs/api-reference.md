# DSER API Reference

This reference documents the public DSER v0.1 surface exported from `dser`. DSER requires Python 3.11 or later.

```python
from dser import (
    ActionResult, AgentResult, AgentTask, Claim, Decision, Disposition,
    DSERAgent, EvidenceLedger, InMemoryStore, MappingVerifier, MemoryRecord,
    PolicyWeights, ReconciliationPolicy, RiskLevel, SourceKind,
    VerificationTool,
)
```

## API map

| Area | Public types | Purpose |
| --- | --- | --- |
| Orchestration | `DSERAgent`, `AgentResult`, `ActionResult` | Run one evidence-reconciliation and optional action cycle. |
| Evidence | `Claim`, `EvidenceLedger`, `SourceKind` | Normalize evidence, retain provenance, and identify conflicts. |
| Task policy | `AgentTask`, `RiskLevel`, `Disposition`, `Decision`, `ReconciliationPolicy`, `PolicyWeights` | Bound a decision and determine the safe disposition. |
| Memory | `MemoryRecord`, `InMemoryStore` | Retrieve candidate context and retain validated outcomes selectively. |
| Verification | `VerificationTool`, `MappingVerifier` | Resolve conflicts against an authoritative source. |

---

## `DSERAgent`

```python
DSERAgent(
    memory: InMemoryStore,
    policy: ReconciliationPolicy,
    verifier: VerificationTool | None = None,
)
```

`DSERAgent` orchestrates one reconciliation cycle. It retrieves memory and obtains current observations concurrently, combines them in an `EvidenceLedger`, invokes the policy, optionally verifies a conflict, optionally calls a typed action executor, and selectively writes a durable memory record.

| Parameter | Type | Description |
| --- | --- | --- |
| `memory` | `InMemoryStore` or compatible adapter | Supplies `retrieve(key)` and `write(record)` behavior. |
| `policy` | `ReconciliationPolicy` | Scores evidence and emits the initial or final decision. |
| `verifier` | `VerificationTool \| None` | Optional authoritative adapter used only when policy returns `VERIFY`. |

### `DSERAgent.decide()`

```python
decide(
    task: AgentTask,
    observations: Iterable[Claim] | Callable[[AgentTask], Iterable[Claim]],
    execute: Callable[[AgentTask, Claim], ActionResult] | None = None,
) -> AgentResult
```

| Parameter | Description |
| --- | --- |
| `task` | Defines the one decision key, goal, risk level, and application metadata. |
| `observations` | Either an iterable of current `Claim` objects or a function that receives `task` and returns claims. |
| `execute` | Optional callback that runs only when final disposition is `ACT` and a claim is selected. |

The agent concurrently evaluates `memory.retrieve(task.key)` and `observations`, then preserves both streams in an `EvidenceLedger`. If policy returns `VERIFY`, the agent calls `verifier.verify(task)` when a verifier is configured. A returned verification claim is added to the ledger and policy runs again. If verification is unavailable, the final disposition becomes `ASK`.

The action callback is not invoked for `PLAN`, `VERIFY`, `ASK`, or `DEFER`. When an `ACT` decision exists, DSER writes a `MemoryRecord` only if it is validated, useful, and source-attributed.

```python
result = agent.decide(
    task,
    observations=lambda task: current_claims_for(task),
    execute=lambda task, claim: ActionResult(
        success=True,
        message=f"Applied {claim.value} for {task.key}",
    ),
)
```

---

## Evidence types

### `Claim`

```python
Claim(
    key: str,
    value: str,
    source: SourceKind,
    authority: float,
    confidence: float,
    relevance: float,
    provenance: str | None = None,
    support: tuple[str, ...] = (),
    observed_at: datetime = datetime.now(UTC),
    expires_at: datetime | None = None,
    identifier: str = uuid4(),
)
```

A normalized proposition about one decision variable. Claims are immutable dataclasses with slots.

| Field | Meaning | Validation / default |
| --- | --- | --- |
| `key` | Stable variable to reconcile, such as `invoice.status`. | Non-empty string. |
| `value` | Canonical asserted value for that variable. | Non-empty string. |
| `source` | Origin category. | A `SourceKind` member. |
| `authority` | Task-specific source priority. | Required float from `0.0` to `1.0`. |
| `confidence` | Reliability of this assertion. | Required float from `0.0` to `1.0`. |
| `relevance` | Directness of this assertion to the task. | Required float from `0.0` to `1.0`. |
| `provenance` | Record ID, document locator, request ID, or source URI. | Optional; strongly recommended. |
| `support` | Short inspectable evidence references. | Empty tuple by default. |
| `observed_at` | Time the assertion was observed. | Current UTC time by default. |
| `expires_at` | Optional hard expiry. | When expired, freshness is `0.0`. |
| `identifier` | Source-record identity used for ledger deduplication. | Random UUID string by default. |

#### `Claim.has_provenance`

```python
claim.has_provenance -> bool
```

Returns `True` when `provenance` is non-empty or `support` is non-empty.

#### `Claim.freshness()`

```python
claim.freshness(
    now: datetime | None = None,
    horizon: timedelta = timedelta(days=30),
) -> float
```

Returns a bounded freshness score from `0.0` to `1.0`. An expired claim returns `0.0`; otherwise score decreases linearly over the configured horizon. Naive timestamps are interpreted as UTC.

### `SourceKind`

| Member | Serialized value | Use it for |
| --- | --- | --- |
| `SYSTEM_OF_RECORD` | `system_of_record` | The authority that owns the present value. |
| `VERIFICATION` | `verification` | A source queried specifically to resolve the current conflict. |
| `TOOL` | `tool` | A generic tool or service response. |
| `USER` | `user` | A user assertion or preference. |
| `DOCUMENT` | `document` | A document-derived fact. |
| `MEMORY` | `memory` | A previously retained episode. |
| `MODEL` | `model` | A model-generated hypothesis or extraction. |

### `EvidenceLedger`

```python
EvidenceLedger(_claims: list[Claim] = [])
```

The ledger stores claims without collapsing their source metadata. `DSERAgent` creates a ledger automatically, but you may use it directly to inspect or test evidence behavior.

| Method | Signature | Behavior |
| --- | --- | --- |
| `add` | `add(claim: Claim) -> None` | Appends a claim unless the same `identifier` is already present. |
| `extend` | `extend(claims: Iterable[Claim]) -> None` | Adds each claim with the same deduplication rule. |
| `for_key` | `for_key(key: str) -> tuple[Claim, ...]` | Returns claims matching one decision key. |
| `all` | `all() -> tuple[Claim, ...]` | Returns all claims in insertion order. |
| `values_for` | `values_for(key: str) -> set[str]` | Returns distinct asserted values for a key. |
| `conflicts_for` | `conflicts_for(key: str) -> tuple[Claim, ...]` | Returns all claims for a key only when more than one distinct value exists; otherwise returns `()`. |
| `grouped` | `grouped() -> dict[str, tuple[Claim, ...]]` | Buckets all claims by decision key. |

---

## Tasks, risks, and decisions

### `AgentTask`

```python
AgentTask(
    key: str,
    goal: str,
    risk: RiskLevel = RiskLevel.LOW,
    permissions: frozenset[str] = frozenset(),
    metadata: dict[str, Any] = {},
)
```

`AgentTask` binds the decision to one key and goal. `key` and `goal` must be non-empty strings.

| Field | Description |
| --- | --- |
| `key` | The claim key policy will reconcile. Claims with other keys remain in the ledger but do not determine the current decision. |
| `goal` | Human-readable objective recorded in retained memory. |
| `risk` | Controls conservative conflict behavior. |
| `permissions` | Application-owned permission labels. The v0.1 reference policy records rather than enforces them. |
| `metadata` | Application-owned context for providers, action executors, and verifiers. |

### `RiskLevel`

| Member | Conflict verification property |
| --- | --- |
| `LOW` | Does not automatically require verification; an insufficient score, missing provenance, or narrow score margin may still return `VERIFY` or `ASK`. |
| `MEDIUM` | `requires_verification_on_conflict` is `True`. |
| `HIGH` | `requires_verification_on_conflict` is `True`. |
| `CRITICAL` | `requires_verification_on_conflict` is `True`; add application-level fail-closed controls and approval. |

### `Disposition`

| Member | Meaning | Typical application response |
| --- | --- | --- |
| `ACT` | Evidence agrees or an authoritative verification resolved the conflict. | Optionally invoke a typed action executor. |
| `PLAN` | A low-risk conflict has a decisive lead but remains visible. | Prepare a reversible next step or seek optional confirmation. |
| `VERIFY` | Policy needs authoritative confirmation. | In `DSERAgent`, this is automatically handed to the configured verifier. |
| `ASK` | Evidence is inadequate, unattributable for a consequential task, or verification was unavailable. | Ask a user or escalate to a human/system owner. |
| `DEFER` | No claim supports the requested decision. | Collect new evidence or halt safely. |

### `Decision`

```python
Decision(
    disposition: Disposition,
    reason: str,
    selected_claim: Claim | None,
    score: float,
    conflicts: tuple[Claim, ...] = (),
    required_evidence: tuple[str, ...] = (),
)
```

`Decision` is the audit record emitted by `ReconciliationPolicy`.

| Field | Description |
| --- | --- |
| `disposition` | The next permitted decision state. |
| `reason` | Human-readable explanation of the policy branch. |
| `selected_claim` | Highest-ranked or verified claim; may be `None` for `DEFER`. |
| `score` | Weighted score for the selected claim. It ranks evidence but does not bypass hard policy rules. |
| `conflicts` | Claims for the task key when multiple values were asserted. |
| `required_evidence` | A short list of evidence needed to proceed when applicable. |

---

## Reconciliation policy

### `PolicyWeights`

```python
PolicyWeights(
    authority: float = 0.30,
    freshness: float = 0.22,
    provenance: float = 0.18,
    confidence: float = 0.15,
    relevance: float = 0.15,
)
```

Weights must sum to `1.0` within a small floating-point tolerance. Invalid totals raise `ValueError`.

### `ReconciliationPolicy`

```python
ReconciliationPolicy(
    weights: PolicyWeights = PolicyWeights(),
    minimum_action_score: float = 0.55,
    decisive_margin: float = 0.12,
)
```

| Parameter | Description |
| --- | --- |
| `weights` | Inputs to the score calculation. |
| `minimum_action_score` | Minimum score needed for a non-conflicting claim to return `ACT`. |
| `decisive_margin` | Required score advantage between first and second ranked claims for a low-risk conflict to avoid mandatory verification. |

#### `ReconciliationPolicy.score()`

```python
score(claim: Claim, now: datetime | None = None) -> float
```

Computes:

```text
authority × authority_weight
+ freshness × freshness_weight
+ provenance_presence × provenance_weight
+ confidence × confidence_weight
+ relevance × relevance_weight
```

#### `ReconciliationPolicy.reconcile()`

```python
reconcile(
    task: AgentTask,
    ledger: EvidenceLedger,
    now: datetime | None = None,
) -> Decision
```

The decision order is deterministic:

1. With no claim for `task.key`, return `DEFER`.
2. Rank claims by weighted score.
3. If multiple values conflict and a source-attributed `VERIFICATION` claim exists, return `ACT` with that verification claim.
4. Otherwise, conflicting medium, high, or critical tasks return `VERIFY`; low-risk conflicts return `VERIFY` when the lead is too narrow or lacks provenance, otherwise `PLAN`.
5. Without conflict, a claim lacking provenance on a medium-or-higher-risk task returns `ASK`.
6. A non-conflicting score below `minimum_action_score` returns `ASK`.
7. Otherwise return `ACT`.

> Scores are ranking inputs, not a safety bypass. A high score does not suppress the hard conflict or provenance rules.

---

## Memory

### `MemoryRecord`

```python
MemoryRecord(
    claim: Claim,
    task_goal: str,
    outcome: str,
    validated: bool,
    useful: bool,
    created_at: datetime = datetime.now(UTC),
)
```

`MemoryRecord` captures an episode that may be retained. Its `eligible_for_retention` property is `True` only when all three conditions hold: `validated`, `useful`, and `claim.has_provenance`.

### `InMemoryStore`

```python
InMemoryStore(_records: list[MemoryRecord] = [])
```

The deterministic reference adapter is suited to demos and tests. It is not durable across process restarts.

| Method | Signature | Behavior |
| --- | --- | --- |
| `retrieve` | `retrieve(key: str, limit: int = 8) -> tuple[Claim, ...]` | Returns matching retained claims, newest first, limited to eight by default. |
| `write` | `write(record: MemoryRecord) -> bool` | Stores a record only when it passes `eligible_for_retention`; returns whether it wrote. |
| `records` | `records() -> tuple[MemoryRecord, ...]` | Returns every retained record for inspection or tests. |

A production replacement should implement compatible `retrieve()` and `write()` methods. It may retrieve candidates through a vector database or document search, but must normalize the final results as `Claim` objects.

---

## Verification

### `VerificationTool`

```python
class VerificationTool(Protocol):
    def verify(self, task: AgentTask) -> Claim | None:
        ...
```

Implement this protocol to connect DSER to a system of record, policy service, approval system, or human-review queue. Return a source-attributed `Claim` to resolve the task’s key; return `None` when authoritative confirmation is unavailable.

### `MappingVerifier`

```python
MappingVerifier(responses: dict[str, Claim] = {})
```

A deterministic verifier for unit tests, examples, and local prototypes. It looks up a response by `task.key`.

```python
verifier = MappingVerifier({
    "order.status": verified_status_claim,
})
```

---

## Results and actions

### `ActionResult`

```python
ActionResult(
    success: bool,
    message: str,
    output: dict[str, Any] = {},
)
```

Return this object from an action executor. `success` determines whether the action outcome is considered useful when DSER evaluates memory retention. `message` should be concise enough for an audit trace. `output` may hold structured, application-specific data.

### `AgentResult`

```python
AgentResult(
    task: AgentTask,
    decision: Decision,
    claims: tuple[Claim, ...],
    action: ActionResult | None,
    verification_used: bool,
    memory_written: bool,
)
```

This is the full outcome of `DSERAgent.decide()`. Store it with your application trace when decisions matter. It gives you the evidence, selected disposition, optional side-effect output, verification-path state, and memory-write outcome in one immutable record.

## Exceptions and integration notes

| Situation | Behavior |
| --- | --- |
| Empty `Claim.key`, `Claim.value`, `AgentTask.key`, or `AgentTask.goal` | Constructor raises `ValueError`. |
| `authority`, `confidence`, or `relevance` outside `0.0..1.0` | `Claim` constructor raises `ValueError`. |
| Policy weights do not total approximately `1.0` | `PolicyWeights` constructor raises `ValueError`. |
| Observation provider, verifier, memory adapter, or action executor raises | The exception propagates; wrap external I/O in your own retry, timeout, and error-handling policy. |
| Verification is needed but unavailable | `DSERAgent` returns an `ASK` decision and does not run the action callback. |
| Action callback returns unsuccessful `ActionResult` | The action remains recorded, but the outcome is not retained by the reference memory policy. |

For end-to-end onboarding, return to the [quickstart](quickstart.md). For architectural intent and non-goals, read the [design document](design.md).
