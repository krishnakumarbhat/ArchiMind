"""Base agent class for ArchiMind archi2 multi-agent system."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentContext(Dict[str, Any]):
    """Simple alias for dict-based context passed between agents."""


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext:
        """Execute the agent's task, returning an updated context."""

    def update_context(self, context: AgentContext, **kwargs: Any) -> AgentContext:
        context.update(kwargs)
        return context
