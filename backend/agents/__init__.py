"""
Deprecated compatibility shim.

Production stage handlers moved to:
- backend.orchestration.stages
- backend.orchestration.context
- backend.orchestration.context_builder
- backend.orchestration.agent_schemas
"""

from backend.orchestration.agent_schemas import (
    AgentArtifact,
    AgentExecutionStatus,
    AgentProposal,
    AgentProposalType,
    AgentRequest,
    AgentRequestType,
    AgentResult,
    AgentUsage,
)
from backend.orchestration.context import (
    AgentContext,
    AgentContextArtifact,
    AgentContextBook,
    AgentContextPolicy,
    AgentContextRuntime,
    AgentContextSource,
    AgentContextUnit,
)
from backend.orchestration.context_builder import (
    AgentContextBuilder,
)
from backend.orchestration.stages import (
    AgentRegistry,
    EditorAgent,
    FinalizerAgent,
    PlannerAgent,
    ReaderAgent,
    ResearchAgent,
    ReviewerAgent,
    ReviserAgent,
    WriterAgent,
)
from backend.orchestration.stages.base import (
    BasePublishingAgent,
)
from backend.orchestration.stages.registry import (
    get_agent_registry,
)

__all__ = [
    "AgentArtifact",
    "AgentContext",
    "AgentContextArtifact",
    "AgentContextBook",
    "AgentContextBuilder",
    "AgentContextPolicy",
    "AgentContextRuntime",
    "AgentContextSource",
    "AgentContextUnit",
    "AgentExecutionStatus",
    "AgentProposal",
    "AgentProposalType",
    "AgentRegistry",
    "AgentRequest",
    "AgentRequestType",
    "AgentResult",
    "AgentUsage",
    "BasePublishingAgent",
    "EditorAgent",
    "FinalizerAgent",
    "PlannerAgent",
    "ReaderAgent",
    "ResearchAgent",
    "ReviewerAgent",
    "ReviserAgent",
    "WriterAgent",
    "get_agent_registry",
]
