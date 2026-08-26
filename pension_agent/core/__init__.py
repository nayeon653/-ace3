"""Shared types, protocols, and exceptions."""

from pension_agent.core.permissions import Permission
from pension_agent.core.retrieval import (
    DocumentType,
    ElementType,
    NeighborRequest,
    RetrievalBackendError,
    RetrievalDataError,
    RetrievalError,
    RetrievedChunk,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchQuery,
)

__all__ = [
    "DocumentType",
    "ElementType",
    "NeighborRequest",
    "Permission",
    "RetrievalBackendError",
    "RetrievalDataError",
    "RetrievalError",
    "RetrievedChunk",
    "SearchFilters",
    "SearchHit",
    "SearchMode",
    "SearchQuery",
]
