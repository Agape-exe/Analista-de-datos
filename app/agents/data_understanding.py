from app.agents.base import SkeletonAgent
from app.application.dto.agent import AgentContext, AgentResult, AgentUpdate


class DataUnderstandingAgent(SkeletonAgent):
    name = "DataUnderstanding"

    async def run(self, context: AgentContext) -> AgentResult:
        if context.input.data_dictionary is not None:
            return self.skipped(AgentUpdate(data_dictionary=context.input.data_dictionary))
        return self.skipped()
