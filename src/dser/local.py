"""Shared local-demo scenarios and JSON-safe DSER result serialization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .agent import DSERAgent
from .memory import InMemoryStore
from .models import ActionResult, AgentResult, AgentTask, Claim, MemoryRecord, RiskLevel, SourceKind
from .policy import ReconciliationPolicy
from .tools import MappingVerifier


def demo_payloads() -> dict[str, dict[str, Any]]:
    """Return copy-safe built-in payloads for local exploration."""

    return {
        "clean": {
            "key": "order.status",
            "goal": "Tell the customer the latest order status.",
            "risk": "low",
            "current_value": "shipped",
            "current_source": "system_of_record",
            "authority": 0.95,
            "confidence": 0.99,
            "relevance": 1.0,
            "provenance": "orders-api:order-123",
            "include_memory": False,
            "memory_value": "",
            "memory_age_days": 30,
            "verify": False,
            "verification_value": "",
            "run_action": True,
        },
        "conflict": {
            "key": "customer.delivery_preference",
            "goal": "Choose the notification channel for a delivery update.",
            "risk": "medium",
            "current_value": "sms",
            "current_source": "system_of_record",
            "authority": 0.95,
            "confidence": 0.99,
            "relevance": 1.0,
            "provenance": "crm-api:customer-42",
            "include_memory": True,
            "memory_value": "email",
            "memory_age_days": 90,
            "verify": True,
            "verification_value": "sms",
            "run_action": True,
        },
        "uncertain": {
            "key": "shipping.address",
            "goal": "Choose the address for a consequential shipment.",
            "risk": "medium",
            "current_value": "1 Main Street",
            "current_source": "user",
            "authority": 0.55,
            "confidence": 0.70,
            "relevance": 1.0,
            "provenance": "",
            "include_memory": False,
            "memory_value": "",
            "memory_age_days": 30,
            "verify": False,
            "verification_value": "",
            "run_action": True,
        },
    }


def _source(value: str) -> SourceKind:
    return SourceKind(value)


def _risk(value: str) -> RiskLevel:
    return RiskLevel(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _number(payload: dict[str, Any], field: str) -> float:
    return float(payload[field])


def _text(payload: dict[str, Any], field: str) -> str:
    return str(payload.get(field, "")).strip()


def _claim_dict(claim: Claim) -> dict[str, Any]:
    return {
        "key": claim.key,
        "value": claim.value,
        "source": claim.source.value,
        "authority": claim.authority,
        "confidence": claim.confidence,
        "relevance": claim.relevance,
        "provenance": claim.provenance,
        "support": list(claim.support),
        "observed_at": claim.observed_at.isoformat(),
        "expires_at": claim.expires_at.isoformat() if claim.expires_at else None,
        "has_provenance": claim.has_provenance,
    }


def result_to_dict(result: AgentResult) -> dict[str, Any]:
    """Convert a local demo result into JSON-safe primitive values."""

    decision = result.decision
    return {
        "task": {
            "key": result.task.key,
            "goal": result.task.goal,
            "risk": result.task.risk.value,
            "permissions": sorted(result.task.permissions),
            "metadata": result.task.metadata,
        },
        "decision": {
            "disposition": decision.disposition.value,
            "reason": decision.reason,
            "score": round(decision.score, 4),
            "selected_claim": _claim_dict(decision.selected_claim) if decision.selected_claim else None,
            "conflicts": [_claim_dict(claim) for claim in decision.conflicts],
            "required_evidence": list(decision.required_evidence),
        },
        "claims": [_claim_dict(claim) for claim in result.claims],
        "action": (
            {"success": result.action.success, "message": result.action.message, "output": result.action.output}
            if result.action
            else None
        ),
        "verification_used": result.verification_used,
        "memory_written": result.memory_written,
    }


def run_local_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one DSER cycle from a local-browser or command-line payload.

    This helper uses only the reference in-memory store and deterministic
    ``MappingVerifier`` so developers can explore DSER without credentials or
    side effects. It raises ``ValueError`` for invalid claim or task input.
    """

    key = _text(payload, "key")
    current_value = _text(payload, "current_value")
    provenance = _text(payload, "provenance") or None
    current_claim = Claim(
        key=key,
        value=current_value,
        source=_source(_text(payload, "current_source") or SourceKind.SYSTEM_OF_RECORD.value),
        authority=_number(payload, "authority"),
        confidence=_number(payload, "confidence"),
        relevance=_number(payload, "relevance"),
        provenance=provenance,
        support=("local-demo:current-observation",) if provenance else (),
    )
    task = AgentTask(
        key=key,
        goal=_text(payload, "goal"),
        risk=_risk(_text(payload, "risk") or RiskLevel.LOW.value),
        permissions=frozenset({"local_demo"}),
    )

    memory = InMemoryStore()
    if _bool(payload.get("include_memory")):
        memory_value = _text(payload, "memory_value")
        if not memory_value:
            raise ValueError("memory_value is required when include_memory is enabled")
        age_days = max(0, int(float(payload.get("memory_age_days", 30))))
        memory_claim = Claim(
            key=key,
            value=memory_value,
            source=SourceKind.MEMORY,
            authority=0.35,
            confidence=0.80,
            relevance=1.0,
            provenance="local-demo:memory-episode",
            support=("local-demo:validated-episode",),
            observed_at=datetime.now(UTC) - timedelta(days=age_days),
        )
        memory.write(
            MemoryRecord(
                claim=memory_claim,
                task_goal="Retain local demo memory.",
                outcome="Stored as a validated local demonstration episode.",
                validated=True,
                useful=True,
            )
        )

    verifier = None
    if _bool(payload.get("verify")):
        verification_value = _text(payload, "verification_value") or current_value
        verification_claim = Claim(
            key=key,
            value=verification_value,
            source=SourceKind.VERIFICATION,
            authority=1.0,
            confidence=1.0,
            relevance=1.0,
            provenance="local-demo:verification-response",
            support=("local-demo:authoritative-confirmation",),
        )
        verifier = MappingVerifier({key: verification_claim})

    agent = DSERAgent(memory=memory, policy=ReconciliationPolicy(), verifier=verifier)
    execute = None
    if _bool(payload.get("run_action", True)):
        execute = lambda _task, claim: ActionResult(
            success=True,
            message=f"Local demo action accepted {claim.key}={claim.value}.",
            output={"applied_key": claim.key, "applied_value": claim.value},
        )
    return result_to_dict(agent.decide(task, observations=(current_claim,), execute=execute))
