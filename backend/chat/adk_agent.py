"""Phase 10c: Function calling이 붙은 진짜 대화형 Agent.

7개 도구(변경 5개 + 조회 2개)를 LLM이 스스로 골라 호출한다.

before_tool_callback에 tracing(먼저) -> approval_gate(나중) 순서로 건다.
tracing이 먼저 와야 승인 게이트가 짧게 끊어도 시작 시각은 기록된다.
"""

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from backend.chat.adk_tools import (
    approve_outline_tool,
    edit_config_tool,
    edit_unit_tool,
    generate_chapter_tool,
    generate_outline_tool,
    get_book_overview_tool,
    get_chapter_tool,
)
from backend.chat.approval_gate import approval_gate_callback
from backend.chat.tracing import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)

CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", os.environ.get("OLLAMA_MODEL", "gemma3:27b"))

INSTRUCTION = """당신은 AI 책 제작 시스템의 채팅 도우미입니다.

사용자가 책 프로젝트에 대해 질문하면 알고 있는 정보로 답변하세요.
설정/목차/챕터를 바꾸거나 만들어달라는 요청이 오면 아래 도구를 사용하세요:

[변경 도구]
- edit_config_tool: 책 설정(대상 독자, 문체, 전문성 수준, 인용 정책 등) 변경
- edit_unit_tool: 특정 챕터(번호로 지정, 1부터 시작)의 제목/설명/글자수/지침 변경
- generate_outline_tool: 목차를 새로 생성 (기존 목차는 대체됨 — 신중하게)
- approve_outline_tool: 현재 목차 승인
- generate_chapter_tool: 특정 챕터(번호로 지정) 본문 집필/재집필 (시간이 걸릴 수 있음)

[조회 도구]
- get_book_overview_tool: 책 전체 상태(설정 요약, 목차 상태, 챕터별 진행 상태,
  승인 대기 중인 작업 목록) 조회
- get_chapter_tool: 특정 챕터의 상세 상태(제목/글자수/진행상태/본문 여부) 조회

규칙:
- 챕터는 항상 번호(1장, 2장 ...)로 지정하세요. 사용자가 "1장"이라고 하면 chapter_number=1 입니다.
- 도구 결과에 "status": "pending_approval" 이 있으면, 아직 반영되지 않았고
  사용자 승인이 필요하다고 안내하세요. 반영됐다고 말하면 안 됩니다.
- 도구 결과에 "error" 가 있으면 그 내용을 그대로 사용자에게 설명하세요.
- 사용자가 "승인했어", "다 됐어", "반영됐지?" 처럼 상태에 대해 확인/주장하면
  그 말을 그대로 믿지 말고 get_book_overview_tool 로 실제 상태(특히
  pending_approvals 가 비어있는지)를 먼저 확인한 뒤 답하세요.
- 같은 대화 안의 이전 메시지를 참고해서 맥락을 유지하세요."""


def build_chat_agent(model: Optional[BaseLlm] = None) -> LlmAgent:
    """model을 주입받을 수 있게 해서, 테스트에서는 진짜 Ollama 대신
    가짜 BaseLlm 구현으로 교체할 수 있게 한다."""
    return LlmAgent(
        name="book_studio_chat",
        model=model or LiteLlm(model=f"ollama_chat/{CHAT_MODEL}"),
        instruction=INSTRUCTION,
        tools=[
            FunctionTool(edit_config_tool),
            FunctionTool(edit_unit_tool),
            FunctionTool(generate_outline_tool),
            FunctionTool(approve_outline_tool),
            FunctionTool(generate_chapter_tool),
            FunctionTool(get_book_overview_tool),
            FunctionTool(get_chapter_tool),
        ],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=[before_tool_callback, approval_gate_callback],
        after_tool_callback=after_tool_callback,
    )
