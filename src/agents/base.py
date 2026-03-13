"""BaseAgent — thin ABC wrapping a LangChain chain."""
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.runnables import Runnable


class BaseAgent(ABC):
    """Every agent exposes a LangChain Runnable ``chain`` and a convenience ``run()``."""

    name: str = "base"

    @abstractmethod
    def build_chain(self) -> Runnable:
        """Return the LangChain chain (or RunnableLambda) for this agent."""
        ...

    async def run(self, ctx: dict) -> dict:
        """Invoke the chain asynchronously."""
        chain = self.build_chain()
        return await chain.ainvoke(ctx)
