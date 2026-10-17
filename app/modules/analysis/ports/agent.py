from typing import Protocol

from app.shared.contracts.agent import AgentContext, AgentResult


class Agent(Protocol):
    """Provider-independent multi-agent stage contract."""

    name: str

    async def run(self, context: AgentContext) -> AgentResult: ...
