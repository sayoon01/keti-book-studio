"""EditorAgent: 설정(config)과 챕터 개별 필드 수정을 담당하는 서브 에이전트."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from backend.chat.adk_tools import edit_config_tool, edit_unit_tool
from backend.chat.approval_gate import approval_gate_callback
from backend.chat.tracing import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)

INSTRUCTION = """당신은 책 설정과 챕터 개별 필드 수정을 담당합니다.

- edit_config_tool: 대상 독자, 문체, 전문성 수준, 인용 정책 등 책 설정 변경
- edit_unit_tool: 특정 챕터(번호로 지정, 1부터 시작)의 제목/설명/글자수/지침 변경

규칙:
- 챕터는 항상 번호로 지정하세요. "1장"이라고 하면 chapter_number=1 입니다.
- 도구 결과에 "status": "pending_approval" 이 있으면, 아직 반영되지 않았고
  사용자 승인이 필요하다고 안내하세요. 반영됐다고 말하면 안 됩니다.
- 도구 결과에 "error" 가 있으면 그 내용을 그대로 사용자에게 설명하세요.
- 이 대화의 범위를 벗어난 요청(목차 생성, 챕터 집필 등)이 오면 조용히
  처리하려 하지 말고, 그 요청은 처리할 수 없다고 명확히 답하세요."""


def build_editor_agent(model) -> LlmAgent:
    return LlmAgent(
        name="editor_agent",
        model=model,
        description="책 설정(대상 독자, 문체 등)이나 특정 챕터의 제목·설명·글자수를 수정한다.",
        instruction=INSTRUCTION,
        tools=[FunctionTool(edit_config_tool), FunctionTool(edit_unit_tool)],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=[before_tool_callback, approval_gate_callback],
        after_tool_callback=after_tool_callback,
    )
