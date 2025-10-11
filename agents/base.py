"""Base agent class for ArchiMind archi2 multi-agent system."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

# Use a type alias for the dict-based context passed between agents.
# This avoids having multiple classes in this file while keeping type clarity.
AgentContext = Dict[str, Any]


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
