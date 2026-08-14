"""Dual-Stream Evidence Reconciliation (DSER) agent framework."""

from .agent import DSERAgent
from .http_fetch import FetchedPage, WebFetchError, fetch_public_page
from .ledger import EvidenceLedger
from .memory import InMemoryStore
from .models import (
    ActionResult,
    AgentResult,
    AgentTask,
    Claim,
    Decision,
    Disposition,
    MemoryRecord,
    RiskLevel,
    SourceKind,
)
from .policy import PolicyWeights, ReconciliationPolicy
from .tools import MappingVerifier, VerificationTool

__all__ = [
    "ActionResult",
    "AgentResult",
    "AgentTask",
    "Claim",
    "Decision",
    "Disposition",
    "DSERAgent",
    "EvidenceLedger",
    "FetchedPage",
    "InMemoryStore",
    "MappingVerifier",
    "MemoryRecord",
    "PolicyWeights",
    "ReconciliationPolicy",
    "RiskLevel",
    "SourceKind",
    "VerificationTool",
    "WebFetchError",
    "fetch_public_page",
]

__version__ = "0.1.0"
