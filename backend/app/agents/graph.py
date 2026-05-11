from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    END = START = StateGraph = None
    LANGGRAPH_AVAILABLE = False


@dataclass
class AgentGraphRuntime:
    """Thin wrapper around LangGraph so the app owns policies and state shape."""

    human_in_the_loop: bool = True

    def available(self) -> bool:
        return LANGGRAPH_AVAILABLE

    def describe(self) -> dict[str, Any]:
        return {
            "runtime": "langgraph",
            "available": LANGGRAPH_AVAILABLE,
            "human_in_the_loop": self.human_in_the_loop,
        }
