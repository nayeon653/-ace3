"""Main, Domain Agent와 API가 공유하는 실행 계약."""

from pension_agent.agent.contracts.answer import AgentAnswer
from pension_agent.agent.contracts.comparison import ComparisonTarget
from pension_agent.agent.contracts.domain import (
    CalculationInputSource,
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
    NumericStatementSourceType,
    VerifiedNumericPlaceholder,
    VerifiedNumericStatement,
    validate_domain_result,
)
from pension_agent.agent.contracts.permissions import (
    Permission,
    document_types_for_permission,
    validate_permission,
)
from pension_agent.agent.contracts.runner import DomainRunner

__all__ = [
    "AgentAnswer",
    "CalculationInputSource",
    "CalculationResult",
    "CatalogItem",
    "CatalogResult",
    "CatalogReturnMode",
    "ComparisonTarget",
    "DecisionStatus",
    "DomainDecision",
    "DomainName",
    "DomainRequest",
    "DomainResult",
    "DomainRunner",
    "DomainToolResult",
    "EvidenceChunk",
    "ExecutionStatus",
    "NumericStatementSourceType",
    "Permission",
    "VerifiedNumericPlaceholder",
    "VerifiedNumericStatement",
    "document_types_for_permission",
    "validate_domain_result",
    "validate_permission",
]
