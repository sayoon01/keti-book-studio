"""
Legacy chapter pipeline.

write → review → revise 시퀀스의 단일 호출 경로다.
REST(api/units.py)와 채팅 도구(chat/adk_tools)가 이 함수를 공유한다.

새 Production 실행은 ProductionEngine과 StageRunner를 사용한다.
기존 API 및 테스트 호환성을 위해 일시적으로 유지한다.

주의: 이 파일은 ADK를 쓰지 않는다. write/review/revise 순서는 판단이 아니라
확정된 시퀀스라서 평범한 Python 함수 호출로 강제한다.
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
