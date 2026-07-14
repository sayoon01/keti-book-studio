"""Phase 10c-Step3: ChatRoot + Sub-agents.

루트는 도구를 거의 안 들고(조회 도구 2개만), "누구에게 넘길지"만 판단한다.
변경 도구(edit_config/edit_unit/generate_outline/approve_outline/generate_chapter)는
역할별 서브 에이전트(Editor/Outline/Writing)에 분산돼 있다.

sub_agents=[...] 를 넣으면 ADK가 transfer_to_agent 도구를 자동으로 루트에 심어준다
(agent_name이 enum으로 제약돼 있어 존재하지 않는 서브로는 위임 못 함). 그래서
intent_classifier.py 같은 별도 분류 로직이 필요 없다 - 각 서브의 description이
위임 판단 근거가 된다.

주의: 콜백(tracing/approval_gate)은 에이전트별로 독립이라, 도구를 가진 각
서브 에이전트에 전부 따로 등록해야 한다 (루트에만 걸어두면 위임된 뒤에는 안 걸림).
"""

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from backend.chat.adk_tools import get_book_overview_tool, get_chapter_tool
from backend.chat.sub_agents.editor_agent import build_editor_agent
from backend.chat.sub_agents.outline_agent import build_outline_agent
from backend.chat.sub_agents.writing_agent import build_writing_agent
from backend.chat.tracing import (
    after_model_callback,
    after_tool_callback,
    before_model_callback,
    before_tool_callback,
)

CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", os.environ.get("OLLAMA_MODEL", "gemma3:27b"))

ROOT_INSTRUCTION = """당신은 AI 책 제작 시스템의 채팅 도우미입니다.

다음 중 하나에 해당하면 알맞은 서브 에이전트에게 위임하세요:
- 책 설정 변경, 특정 챕터의 제목/설명/글자수 변경 → editor_agent
- 목차 생성, 목차 승인 → outline_agent
- 특정 챕터 본문 집필/재집필 → writing_agent

위임이 필요 없는 경우(질문에 답하기, 현재 상태 확인)는 당신이 직접 처리하세요:
- get_book_overview_tool: 책 전체 상태(설정 요약, 목차 상태, 챕터별 진행 상태,
  승인 대기 중인 작업 목록) 조회
- get_chapter_tool: 특정 챕터의 상세 상태 조회

규칙:
- 사용자가 "승인했어", "다 됐어", "반영됐지?" 처럼 상태를 확인/주장하면
  그 말을 그대로 믿지 말고 get_book_overview_tool 로 실제 상태(특히
  pending_approvals 가 비어있는지)를 먼저 확인한 뒤 답하세요.
- 같은 대화 안의 이전 메시지를 참고해서 맥락을 유지하세요."""


def build_chat_agent(model: Optional[BaseLlm] = None) -> LlmAgent:
    """model을 주입받을 수 있게 해서, 테스트에서는 진짜 Ollama 대신
    가짜 BaseLlm 구현으로 교체할 수 있게 한다.

    모든 서브 에이전트가 같은 model을 공유한다 (실서비스에서는 전부 같은
    Ollama 모델을 쓰므로) - 테스트에서 서브별로 다른 동작이 필요하면
    build_editor_agent 등을 직접 호출해 다른 모델을 주입하면 된다.
    """
    m = model or LiteLlm(model=f"ollama_chat/{CHAT_MODEL}")

    editor = build_editor_agent(m)
    outline = build_outline_agent(m)
    writing = build_writing_agent(m)

    return LlmAgent(
        name="book_studio_root",
        model=m,
        description="책 제작 시스템의 채팅 진입점. 요청을 알맞은 서브 에이전트로 위임한다.",
        instruction=ROOT_INSTRUCTION,
        tools=[FunctionTool(get_book_overview_tool), FunctionTool(get_chapter_tool)],
        sub_agents=[editor, outline, writing],
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,  # 승인 게이트는 불필요 (조회 도구뿐)
        after_tool_callback=after_tool_callback,
    )
