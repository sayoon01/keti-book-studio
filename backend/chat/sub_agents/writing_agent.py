"""WritingAgent: 챕터 본문 집필을 담당하는 서브 에이전트.

generate_chapter_tool 내부에서 orchestration/chapter_pipeline.py::run_chapter_pipeline()
(write -> review -> revise, 순수 함수)을 호출한다 — 여기서도 ADK는 "위임 판단"까지만
관여하고, 실제 집필 순서는 여전히 평범한 함수 호출이다.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from backend.chat.adk_tools import generate_chapter_tool
from backend.chat.approval_gate import approval_gate_callback
from backend.chat.tracing import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)

INSTRUCTION = """당신은 챕터 본문 집필을 담당합니다.

- generate_chapter_tool: 특정 챕터(번호로 지정, 1부터 시작) 본문을 집필/재집필합니다.
  목차가 승인된 상태여야 하고, 시간이 걸릴 수 있다고 미리 안내하세요.

규칙:
- 챕터는 항상 번호로 지정하세요. "3장 써줘"라고 하면 chapter_number=3 입니다.
- 도구 결과에 "status": "pending_approval" 이 있으면 아직 집필이 시작되지 않았고
  승인이 필요하다고 안내하세요.
- 도구 결과에 "error" 가 있으면(예: 목차 미승인) 그 내용을 그대로 설명하세요.
- 이 대화의 범위를 벗어난 요청(설정 변경, 목차 생성 등)이 오면
  처리할 수 없다고 명확히 답하세요."""


def build_writing_agent(model) -> LlmAgent:
    return LlmAgent(
        name="writing_agent",
        model=model,
        description="특정 챕터의 본문을 집필하거나 재집필한다.",
        instruction=INSTRUCTION,
        tools=[FunctionTool(generate_chapter_tool)],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=[before_tool_callback, approval_gate_callback],
        after_tool_callback=after_tool_callback,
    )
