"""Main, Domain Agent와 API가 공유하는 실행 계약."""

from pension_agent.agent.contracts.answer import AgentAnswer
from pension_agent.agent.contracts.domain import (
    CalculationResult,
    CatalogItem,
    CatalogResult,
    CatalogReturnMode,
    DecisionStatus,
    DomainDecision,
    DomainName,
    DomainRequest,
    DomainResult,
    DomainToolResult,
    EvidenceChunk,
    ExecutionStatus,
    validate_domain_result,
)
from pension_agent.agent.contracts.permissions import (
    Permission,
    document_types_for_permission,
    validate_permission,
)

__all__ = [
    "AgentAnswer",
    "CalculationResult",
    "CatalogItem",
    "CatalogResult",
    "CatalogReturnMode",
    "DecisionStatus",
    "DomainDecision",
    "DomainName",
    "DomainRequest",
    "DomainResult",
    "DomainToolResult",
    "EvidenceChunk",
    "ExecutionStatus",
    "Permission",
    "document_types_for_permission",
    "validate_domain_result",
    "validate_permission",
]
