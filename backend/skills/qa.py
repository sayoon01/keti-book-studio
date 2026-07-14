"""QA Agent (Answer Mode).

역할: 자료/책 내용에 대한 질문에 답한다. 아무것도 바꾸지 않으므로
승인 절차 없이 즉시 실행된다.
"""

from typing import Callable

LlmCall = Callable[[str, str], str]

SYSTEM_PROMPT = """당신은 책 프로젝트의 자료와 내용에 대해 답변하는 도우미입니다.
주어진 자료와 챕터 내용을 근거로만 답변하세요. 근거 없는 내용을 지어내지 마세요.
간결하게 답변하세요."""


def build_user_prompt(message: str, context_text: str) -> str:
    return f"참고 자료/내용:\n{context_text}\n\n질문: {message}"


def answer_question(*, message: str, context_text: str, llm_call: LlmCall) -> str:
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(message, context_text))
    return raw.strip()
