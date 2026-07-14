"""챕터 생성 순서(write -> review -> revise)의 단일 소유자.

REST(api/units.py::generate_unit_body)와 채팅 도구(chat/adk_tools.py::generate_chapter_tool)가
이 함수 하나를 공유한다 — Phase7~10c에서 지켜온 "실행 경로 하나" 원칙을 그대로 유지.

주의: 이 파일은 ADK를 쓰지 않는다. write/review/revise 순서는 판단이 아니라
확정된 시퀀스라서(Reviewer가 "검토 생략" 판단을 할 여지를 주면 안 됨), 그냥
평범한 Python 함수 호출로 강제하는 게 맞다 — SequentialAgent로 승격하지 않기로
한 결정은 마법사 경로까지 ADK 세션 오버헤드가 번지는 걸 막기 위함.
"""

from backend.skills.reviewer import review_chapter
from backend.skills.reviser import revise_chapter
from backend.skills.writer import write_chapter


def run_chapter_pipeline(
    *,
    unit: dict,
    book_config: dict,
    persona_writer_md: str,
    persona_reviewer_md: str,
    evidence_chunks: list[str],
    writer_llm,
    reviewer_llm,
    reviser_llm,
) -> dict:
    """write -> review -> (필요시) revise 를 실행하고 결과를 반환한다.

    반환값의 body_md/review/revised 는 기존 generate_unit_body()가 만들던 것과
    동일한 모양이다 (호출부에서 그대로 unit.body_md 등에 대입하면 됨).
    """
    body_md = write_chapter(
        unit=unit,
        book_config=book_config,
        persona_writer_md=persona_writer_md,
        evidence_chunks=evidence_chunks,
        llm_call=writer_llm,
    )

    review_result = review_chapter(
        body_md=body_md,
        unit=unit,
        persona_reviewer_md=persona_reviewer_md,
        evidence_chunks=evidence_chunks,
        llm_call=reviewer_llm,
    )

    final_body = body_md
    revised = False
    if review_result["needs_revision"] and review_result["issues"]:
        final_body = revise_chapter(
            body_md=body_md,
            issues=review_result["issues"],
            unit=unit,
            persona_writer_md=persona_writer_md,
            llm_call=reviser_llm,
        )
        revised = True

    return {"body_md": final_body, "review": review_result, "revised": revised}
