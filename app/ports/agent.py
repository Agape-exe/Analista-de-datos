from typing import Protocol

from app.application.dto.agent import AgentContext, AgentResult


class Agent(Protocol):
    """Provider-independent multi-agent stage contract."""

    name: str

    async def run(self, context: AgentContext) -> AgentResult: ...
