"""Central registry facilitating dynamic lookup and runtime switching of ASP adapters."""

from __future__ import annotations

from typing import Dict, List

from finkraft.adapters.base import ASPAdapter
from finkraft.exceptions import ASPAdapterNotFoundError


class ASPRegistry:
    """
    Central registry for ASP adapters.
    Allows dynamic registration, retrieval, and switching across ASPs.
    """
    _adapters: Dict[str, ASPAdapter] = {}

    @classmethod
    def register(cls, asp_id: str, adapter: ASPAdapter) -> None:
        """Registers an ASP adapter under a unique identifier."""
        cls._adapters[asp_id] = adapter

    @classmethod
    def get(cls, asp_id: str) -> ASPAdapter:
        """Retrieves an ASP adapter by identifier. Raises ASPAdapterNotFoundError if missing."""
        if asp_id not in cls._adapters:
            raise ASPAdapterNotFoundError(asp_id)
        return cls._adapters[asp_id]

    @classmethod
    def list_available(cls) -> List[str]:
        """Lists all registered ASP identifiers."""
        return list(cls._adapters.keys())

    @classmethod
    def clear(cls) -> None:
        """Clears registered adapters (primarily for testing)."""
        cls._adapters.clear()
