"""OutlineAgent: 목차 생성/승인을 담당하는 서브 에이전트."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from backend.chat.adk_tools import approve_outline_tool, generate_outline_tool
from backend.chat.approval_gate import approval_gate_callback
from backend.chat.tracing import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)

INSTRUCTION = """당신은 책 목차 생성과 승인을 담당합니다.

- generate_outline_tool: 목차를 새로 생성한다. 기존 목차는 전부 대체되니
  사용자가 확실히 원할 때만 호출하세요.
- approve_outline_tool: 현재 목차를 승인한다. 승인 후에만 챕터 집필이 가능합니다.

규칙:
- 두 도구 모두 항상 사용자 승인을 거칩니다 — 도구 결과에
  "status": "pending_approval" 이 있으면 아직 반영 안 됐다고 안내하세요.
- 이 대화의 범위를 벗어난 요청(설정 변경, 챕터 집필 등)이 오면
  처리할 수 없다고 명확히 답하세요."""


def build_outline_agent(model) -> LlmAgent:
    return LlmAgent(
        name="outline_agent",
        model=model,
        description="책 목차를 새로 생성하거나, 만들어진 목차를 승인한다.",
        instruction=INSTRUCTION,
        tools=[FunctionTool(generate_outline_tool), FunctionTool(approve_outline_tool)],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=[before_tool_callback, approval_gate_callback],
        after_tool_callback=after_tool_callback,
    )
