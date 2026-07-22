from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.orchestration.agent_schemas import AgentRequest
from backend.publishing.enums import (
    ProductionArtifactType,
)


class AgentContextArtifact(BaseModel):
    """
    Agent 실행에 전달되는 입력 Artifact.

    DB의 ProductionArtifact를 Agent가 사용하기 쉬운
    Context 전용 구조로 변환한 객체다.
    """

    artifact_id: str

    # DB 및 기존 코드와의 호환성을 위해 str로 유지한다.
    # ProductionArtifactType도 StrEnum이므로 문자열로 직렬화할 수 있다.
    artifact_type: str

    name: str

    content: dict[str, Any] = Field(
        default_factory=dict
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    created_by_role: str | None = None

    def matches_type(
        self,
        artifact_type: ProductionArtifactType | str,
    ) -> bool:
        """
        현재 Artifact가 지정한 타입과 같은지 확인한다.

        문자열과 ProductionArtifactType을 모두 지원한다.
        """

        expected = _enum_value(
            artifact_type
        )

        actual = _enum_value(
            self.artifact_type
        )

        return actual == expected


class AgentContextSource(BaseModel):
    """
    Agent가 참조할 수 있는 Source 정보.
    """

    source_id: str

    title: str
    source_type: str

    text_content: str = ""

    summary: str | None = None

    keywords: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextUnit(BaseModel):
    """
    현재 Agent가 작업하는 챕터 또는 Unit.
    """

    unit_id: str

    title: str
    description: str | None = None

    order_index: int = 0

    status: str | None = None

    target_length: int | None = None

    required_topics: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextBook(BaseModel):
    """
    현재 ProductionRun의 책 정보.
    """

    book_id: str

    title: str

    description: str | None = None
    target_reader: str | None = None
    purpose: str | None = None
    language: str = "ko"

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextPolicy(BaseModel):
    """
    Agent 실행 시 적용하는 Persona 및 정책.
    """

    persona_name: str | None = None

    common_instruction: str = ""
    role_instruction: str = ""

    writing_style: str | None = None
    review_policy: str | None = None
    visual_policy: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContextRuntime(BaseModel):
    """
    현재 AgentTask의 실행 정보.
    """

    run_id: str
    stage_id: str
    task_id: str

    workspace_id: str

    stage_key: str
    stage_type: str

    agent_role: str
    agent_name: str

    attempt: int = 1
    max_retries: int = 1

    automation_level: str = "BALANCED"

    runtime_state: dict[str, Any] = Field(
        default_factory=dict
    )


class AgentContext(BaseModel):
    """
    Publishing Agent에 전달되는 Shared Blackboard View.

    Workspace 정보와 현재 Task 실행 정보,
    Source 및 이전 Stage의 Artifact를 함께 제공한다.
    """

    runtime: AgentContextRuntime

    book: AgentContextBook

    unit: AgentContextUnit | None = None

    request: AgentRequest = Field(
        default_factory=AgentRequest
    )

    policy: AgentContextPolicy = Field(
        default_factory=AgentContextPolicy
    )

    sources: list[AgentContextSource] = Field(
        default_factory=list
    )

    input_artifacts: list[
        AgentContextArtifact
    ] = Field(
        default_factory=list
    )

    shared_state: dict[str, Any] = Field(
        default_factory=dict
    )

    def get_artifacts_by_type(
        self,
        artifact_type: ProductionArtifactType | str,
    ) -> list[AgentContextArtifact]:
        """
        지정한 타입의 입력 Artifact를 모두 반환한다.

        다음 두 방식 모두 지원한다.

        context.get_artifacts_by_type(
            ProductionArtifactType.CHAPTER_PLAN
        )

        context.get_artifacts_by_type(
            "CHAPTER_PLAN"
        )
        """

        expected = _enum_value(
            artifact_type
        )

        return [
            artifact
            for artifact in self.input_artifacts
            if _enum_value(
                artifact.artifact_type
            )
            == expected
        ]

    def get_latest_artifact(
        self,
        artifact_type: ProductionArtifactType | str,
    ) -> AgentContextArtifact | None:
        """
        지정한 타입의 Artifact 중 가장 마지막 Artifact를 반환한다.

        현재 AgentContextArtifact에 version 또는 created_at 필드가
        없으므로 input_artifacts의 순서를 기준으로 판단한다.

        ContextBuilder가 Artifact를 시간순 또는 버전순으로 넣는다는
        전제에서 마지막 항목을 최신 Artifact로 사용한다.
        """

        matches = self.get_artifacts_by_type(
            artifact_type
        )

        if not matches:
            return None

        return matches[-1]

    def has_artifact(
        self,
        artifact_type: ProductionArtifactType | str,
    ) -> bool:
        """
        지정한 타입의 Artifact가 하나 이상 있는지 확인한다.
        """

        return (
            self.get_latest_artifact(
                artifact_type
            )
            is not None
        )

    def require_artifact(
        self,
        artifact_type: ProductionArtifactType | str,
    ) -> AgentContextArtifact:
        """
        필수 Artifact를 가져온다.

        없으면 명확한 예외를 발생시킨다.
        Skill 내부에서 필수 입력을 읽을 때 사용할 수 있다.
        """

        artifact = self.get_latest_artifact(
            artifact_type
        )

        if artifact is None:
            artifact_name = _enum_value(
                artifact_type
            )

            raise ValueError(
                "필수 입력 Artifact가 없습니다: "
                f"{artifact_name}"
            )

        return artifact


def _enum_value(
    value: Enum | str,
) -> str:
    """
    Enum 또는 문자열을 비교 가능한 문자열로 변환한다.

    StrEnum은 str을 상속하지만 str(enum)을 사용하면
    구현에 따라 'ProductionArtifactType.CHAPTER_PLAN'처럼
    표현될 가능성을 피하기 위해 value 속성을 우선 사용한다.
    """

    if isinstance(value, Enum):
        return str(value.value)

    return str(value)
