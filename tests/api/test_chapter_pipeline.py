"""orchestration/chapter_pipeline.py 완료 조건 테스트.

API 레이어(units.py) 없이 run_chapter_pipeline()을 직접 호출해서 검증한다.
기존 test_writer_pipeline.py(API 레벨)가 그대로 통과하는 것과 별개로,
orchestration 레이어 자체도 독립적으로 테스트 가능해야 한다는 걸 보여주는 목적.
"""

import json

from backend.orchestration.chapter_pipeline import run_chapter_pipeline

_UNIT = {
    "unit_id": "unit-1",
    "title": "1장. 개요",
    "description": "ALD 공정 개요",
    "target_characters": 1000,
    "must_cover": [],
}
_CONFIG = {"tone": "전문적", "expertise_level": "중급"}


def _writer_llm(system_prompt: str, user_prompt: str) -> str:
    return "# 1장\n\nALD 공정은 원자층 단위로 박막을 증착하는 기술이다."


def _reviewer_llm_no_issues(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({"issues": [], "needs_revision": False, "overall_comment": "문제 없음"})


def _reviewer_llm_with_issues(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {
            "issues": [{"location": "1문단", "problem": "근거 부족", "suggestion": "출처 추가"}],
            "needs_revision": True,
            "overall_comment": "근거 보강 필요",
        }
    )


def _reviser_llm(system_prompt: str, user_prompt: str) -> str:
    return "# 1장 (수정)\n\nALD 공정은 원자층 단위로 박막을 증착하는 기술이다. [출처: XYZ]"


def _fail_if_called(system_prompt: str, user_prompt: str) -> str:
    raise AssertionError("이 LLM은 호출되면 안 됩니다")


def test_pipeline_skips_reviser_when_no_issues():
    result = run_chapter_pipeline(
        unit=_UNIT, book_config=_CONFIG,
        persona_writer_md="", persona_reviewer_md="",
        evidence_chunks=["ALD는 자기제한 반응이다."],
        writer_llm=_writer_llm,
        reviewer_llm=_reviewer_llm_no_issues,
        reviser_llm=_fail_if_called,
    )
    assert result["revised"] is False
    assert "원자층 단위로 박막을 증착" in result["body_md"]
    assert result["review"]["needs_revision"] is False


def test_pipeline_calls_reviser_when_issues_found():
    result = run_chapter_pipeline(
        unit=_UNIT, book_config=_CONFIG,
        persona_writer_md="", persona_reviewer_md="",
        evidence_chunks=["ALD는 자기제한 반응이다."],
        writer_llm=_writer_llm,
        reviewer_llm=_reviewer_llm_with_issues,
        reviser_llm=_reviser_llm,
    )
    assert result["revised"] is True
    assert "[출처: XYZ]" in result["body_md"]
    assert len(result["review"]["issues"]) == 1


def test_pipeline_return_shape_matches_api_layer_expectation():
    """units.py가 이 반환값을 그대로 unit.body_md 등에 대입하므로 키 이름이 고정돼야 한다."""
    result = run_chapter_pipeline(
        unit=_UNIT, book_config=_CONFIG,
        persona_writer_md="", persona_reviewer_md="",
        evidence_chunks=["증거"],
        writer_llm=_writer_llm,
        reviewer_llm=_reviewer_llm_no_issues,
        reviser_llm=_fail_if_called,
    )
    assert set(result.keys()) == {"body_md", "review", "revised"}
