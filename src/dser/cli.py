"""Interactive and scriptable terminal interface for local DSER decisions."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .local import demo_payloads, run_local_decision
from .models import RiskLevel, SourceKind


def _prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def _yes_no(label: str, default: bool) -> bool:
    marker = "Y/n" if default else "y/N"
    value = input(f"{label} ({marker}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def interactive_payload() -> dict[str, Any]:
    """Collect a local DSER decision payload from standard input."""

    print("\nDSER Local CLI — create one evidence-reconciliation decision.\n")
    key = _prompt("Decision key", "customer.delivery_preference")
    goal = _prompt("Goal", "Choose the channel for a delivery update")
    risk = _prompt("Risk (low, medium, high, critical)", RiskLevel.MEDIUM.value)
    source = _prompt(
        "Current source (system_of_record, tool, user, document, model)",
        SourceKind.SYSTEM_OF_RECORD.value,
    )
    current_value = _prompt("Current value", "sms")
    authority = _prompt("Authority from 0 to 1", "0.95")
    confidence = _prompt("Confidence from 0 to 1", "0.99")
    relevance = _prompt("Relevance from 0 to 1", "1.0")
    provenance = _prompt("Provenance or record ID (leave blank to test missing provenance)", "crm-api:customer-42")

    include_memory = _yes_no("Include a remembered value", True)
    memory_value = ""
    memory_age_days = 30
    if include_memory:
        memory_value = _prompt("Remembered value", "email")
        memory_age_days = _prompt("Age of remembered value in days", "90")

    fetch_url = _prompt("Public HTTP(S) URL to fetch as document evidence (optional)", "")

    verify = _yes_no("Enable authoritative verification on conflict", True)
    verification_value = ""
    if verify:
        verification_value = _prompt("Verified value", current_value)

    return {
        "key": key,
        "goal": goal,
        "risk": risk,
        "current_source": source,
        "current_value": current_value,
        "authority": authority,
        "confidence": confidence,
        "relevance": relevance,
        "provenance": provenance,
        "include_memory": include_memory,
        "memory_value": memory_value,
        "memory_age_days": memory_age_days,
        "verify": verify,
        "verification_value": verification_value,
        "run_action": _yes_no("Run the safe local demo action if DSER permits it", True),
        "fetch_url": fetch_url,
    }


def _print_result(result: dict[str, Any]) -> None:
    decision = result["decision"]
    selected = decision["selected_claim"]
    print("\n" + "=" * 66)
    print(f"DSER disposition: {decision['disposition'].upper()}")
    print(f"Reason: {decision['reason']}")
    print(f"Evidence score: {decision['score']}")
    if selected:
        print(f"Selected claim: {selected['key']} = {selected['value']} ({selected['source']})")
    if decision["conflicts"]:
        values = ", ".join(f"{item['value']} ({item['source']})" for item in decision["conflicts"])
        print(f"Conflicting evidence: {values}")
    if decision["required_evidence"]:
        print("Required evidence: " + "; ".join(decision["required_evidence"]))
    if result.get("web_fetch"):
        fetched = result["web_fetch"]
        print(f"HTTP source: {fetched['title'] or 'Untitled document'} ({fetched['content_type']}, HTTP {fetched['status_code']})")
        print(f"Fetched URL: {fetched['final_url']}")
    if result["action"]:
        print(f"Action: {result['action']['message']}")
    else:
        print("Action: no local action ran")
    print(f"Verification used: {result['verification_used']}")
    print(f"Memory written: {result['memory_written']}")
    print("=" * 66)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dser-cli",
        description="Run DSER evidence-reconciliation decisions locally.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(demo_payloads()),
        default="conflict",
        help="Run a built-in deterministic scenario (default: conflict).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for a custom local decision payload.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete decision trace as JSON.",
    )
    parser.add_argument(
        "--url",
        help="Fetch a public HTTP(S) page and use its text as source-attributed document evidence.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = interactive_payload() if args.interactive else demo_payloads()[args.scenario]
    if args.url:
        payload["fetch_url"] = args.url
    try:
        result = run_local_decision(payload)
    except (TypeError, ValueError) as exc:
        print(f"DSER input error: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
