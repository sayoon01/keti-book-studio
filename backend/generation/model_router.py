from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class GenerationRole(str, Enum):
    """
    Book Studio Generation Engine에서 사용하는 역할.

    각 역할은 ModelRouter를 통해 자신에게 맞는
    모델과 생성 설정을 전달받는다.
    """

    RESEARCHER = "researcher"
    PLANNER = "planner"
    WRITER = "writer"
    REVIEWER = "reviewer"
    TECHNICAL_REVIEWER = "technical_reviewer"
    EDITOR = "editor"
    REVISER = "reviser"
    READER = "reader"


@dataclass(frozen=True, slots=True)
class RoleModelConfig:
    """
    하나의 Generation Role이 사용할 모델 설정.

    Attributes:
        role:
            Researcher, Writer, Reviewer 등의 역할.

        model:
            Ollama에 등록된 모델 이름.

        temperature:
            생성 다양성 설정.

        timeout_seconds:
            해당 역할의 Ollama 요청 제한 시간.

        num_predict:
            최대 출력 토큰 수.

        num_ctx:
            Ollama Context 크기.

        response_format:
            json 또는 markdown.

        enabled:
            해당 역할 사용 여부.
    """

    role: GenerationRole
    model: str
    temperature: float
    timeout_seconds: float
    num_predict: int
    num_ctx: int
    response_format: str
    enabled: bool = True


class ModelRouter:
    """
    역할에 따라 적절한 Ollama 모델 설정을 반환한다.

    Generation Service는 모델 이름을 직접 결정하지 않고
    반드시 ModelRouter를 통해 설정을 조회한다.

    Example:
        router = ModelRouter()

        writer_config = router.get_config(
            GenerationRole.WRITER
        )

        print(writer_config.model)
        # gemma4:31b
    """

    def __init__(self) -> None:
        self._configs = self._build_configs()

    def get_config(
        self,
        role: GenerationRole,
    ) -> RoleModelConfig:
        """
        역할에 해당하는 모델 설정을 반환한다.
        """

        if not isinstance(role, GenerationRole):
            raise TypeError(
                "role은 GenerationRole이어야 합니다. "
                f"actual={type(role).__name__}"
            )

        config = self._configs.get(role)

        if config is None:
            raise KeyError(
                "등록되지 않은 Generation Role입니다. "
                f"role={role.value}"
            )

        if not config.enabled:
            raise RuntimeError(
                "현재 비활성화된 Generation Role입니다. "
                f"role={role.value}"
            )

        return config

    def get_model(
        self,
        role: GenerationRole,
    ) -> str:
        """
        역할에 연결된 모델 이름만 반환한다.
        """

        return self.get_config(role).model

    def is_enabled(
        self,
        role: GenerationRole,
    ) -> bool:
        """
        해당 역할의 활성화 여부를 반환한다.
        """

        config = self._configs.get(role)

        if config is None:
            return False

        return config.enabled

    def list_configs(
        self,
    ) -> list[RoleModelConfig]:
        """
        모든 역할별 설정을 목록으로 반환한다.
        """

        return list(self._configs.values())

    def as_dict(
        self,
    ) -> dict[str, dict[str, object]]:
        """
        API 응답이나 디버깅에 사용할 수 있는
        dictionary 형식으로 반환한다.
        """

        result: dict[str, dict[str, object]] = {}

        for role, config in self._configs.items():
            result[role.value] = {
                "model": config.model,
                "temperature": config.temperature,
                "timeout_seconds": config.timeout_seconds,
                "num_predict": config.num_predict,
                "num_ctx": config.num_ctx,
                "response_format": config.response_format,
                "enabled": config.enabled,
            }

        return result

    @staticmethod
    def requires_technical_review(
        *,
        book_type: str | None = None,
        chapter_text: str | None = None,
    ) -> bool:
        """
        Technical Reviewer 실행 여부를 판단한다.

        다음 유형의 책이나 챕터일 때만 Technical Reviewer를 사용한다.

        - programming
        - api
        - system_design
        - software_engineering
        - code

        book_type 정보가 없더라도 Markdown 코드 블록이
        포함되어 있다면 Technical Reviewer를 사용할 수 있다.
        """

        normalized_book_type = (
            book_type.strip().lower()
            if isinstance(book_type, str)
            else ""
        )

        technical_types = {
            "programming",
            "programming_book",
            "api",
            "api_documentation",
            "system_design",
            "software_engineering",
            "developer_guide",
            "code",
            "technical",
            "기술서",
            "프로그래밍",
            "시스템 설계",
            "api 문서",
        }

        if normalized_book_type in technical_types:
            return True

        if isinstance(chapter_text, str):
            if "```" in chapter_text:
                return True

        return False

    def _build_configs(
        self,
    ) -> dict[GenerationRole, RoleModelConfig]:
        """
        환경변수를 읽어 전체 역할 설정을 만든다.
        """

        return {
            GenerationRole.RESEARCHER: RoleModelConfig(
                role=GenerationRole.RESEARCHER,
                model=_read_str_env(
                    "BOOK_STUDIO_RESEARCHER_MODEL",
                    "qwen3:32b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_RESEARCHER_TEMPERATURE",
                    0.2,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_RESEARCHER_TIMEOUT_SECONDS",
                    300.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_RESEARCHER_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_RESEARCHER_NUM_CTX",
                    8192,
                ),
                response_format="json",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_RESEARCHER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.PLANNER: RoleModelConfig(
                role=GenerationRole.PLANNER,
                model=_read_str_env(
                    "BOOK_STUDIO_PLANNER_MODEL",
                    "qwen3:32b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_PLANNER_TEMPERATURE",
                    0.2,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_PLANNER_TIMEOUT_SECONDS",
                    300.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_PLANNER_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_PLANNER_NUM_CTX",
                    8192,
                ),
                response_format="json",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_PLANNER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.WRITER: RoleModelConfig(
                role=GenerationRole.WRITER,
                model=_read_str_env(
                    "BOOK_STUDIO_WRITER_MODEL",
                    "gemma4:31b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_WRITER_TEMPERATURE",
                    0.4,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_WRITER_TIMEOUT_SECONDS",
                    600.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_WRITER_NUM_PREDICT",
                    3072,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_WRITER_NUM_CTX",
                    8192,
                ),
                response_format="markdown",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_WRITER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.REVIEWER: RoleModelConfig(
                role=GenerationRole.REVIEWER,
                model=_read_str_env(
                    "BOOK_STUDIO_REVIEWER_MODEL",
                    "qwen3:32b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_REVIEWER_TEMPERATURE",
                    0.1,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_REVIEWER_TIMEOUT_SECONDS",
                    300.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_REVIEWER_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_REVIEWER_NUM_CTX",
                    8192,
                ),
                response_format="json",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_REVIEWER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.TECHNICAL_REVIEWER: RoleModelConfig(
                role=GenerationRole.TECHNICAL_REVIEWER,
                model=_read_str_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_MODEL",
                    "qwen3-coder:30b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_TEMPERATURE",
                    0.1,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_TIMEOUT_SECONDS",
                    300.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_NUM_CTX",
                    8192,
                ),
                response_format="json",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_TECHNICAL_REVIEWER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.EDITOR: RoleModelConfig(
                role=GenerationRole.EDITOR,
                model=_read_str_env(
                    "BOOK_STUDIO_EDITOR_MODEL",
                    "gemma4:31b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_EDITOR_TEMPERATURE",
                    0.3,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_EDITOR_TIMEOUT_SECONDS",
                    600.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_EDITOR_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_EDITOR_NUM_CTX",
                    16384,
                ),
                response_format="markdown",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_EDITOR_ENABLED",
                    True,
                ),
            ),

            GenerationRole.REVISER: RoleModelConfig(
                role=GenerationRole.REVISER,
                model=_read_str_env(
                    "BOOK_STUDIO_REVISER_MODEL",
                    "gemma4:31b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_REVISER_TEMPERATURE",
                    0.3,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_REVISER_TIMEOUT_SECONDS",
                    600.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_REVISER_NUM_PREDICT",
                    3072,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_REVISER_NUM_CTX",
                    8192,
                ),
                response_format="markdown",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_REVISER_ENABLED",
                    True,
                ),
            ),

            GenerationRole.READER: RoleModelConfig(
                role=GenerationRole.READER,
                model=_read_str_env(
                    "BOOK_STUDIO_READER_MODEL",
                    "qwen3:32b",
                ),
                temperature=_read_float_env(
                    "BOOK_STUDIO_READER_TEMPERATURE",
                    0.3,
                ),
                timeout_seconds=_read_float_env(
                    "BOOK_STUDIO_READER_TIMEOUT_SECONDS",
                    300.0,
                ),
                num_predict=_read_int_env(
                    "BOOK_STUDIO_READER_NUM_PREDICT",
                    2048,
                ),
                num_ctx=_read_int_env(
                    "BOOK_STUDIO_READER_NUM_CTX",
                    8192,
                ),
                response_format="json",
                enabled=_read_bool_env(
                    "BOOK_STUDIO_READER_ENABLED",
                    True,
                ),
            ),
        }


def _read_str_env(
    name: str,
    fallback: str,
) -> str:
    value = os.getenv(name)

    if value is None:
        return fallback

    normalized = value.strip()

    return normalized or fallback


def _read_int_env(
    name: str,
    fallback: int,
) -> int:
    value = os.getenv(name)

    if value is None or not value.strip():
        return fallback

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name}은 정수여야 합니다. "
            f"actual={value!r}"
        ) from exc

    if parsed <= 0:
        raise ValueError(
            f"{name}은 0보다 커야 합니다. "
            f"actual={parsed}"
        )

    return parsed


def _read_float_env(
    name: str,
    fallback: float,
) -> float:
    value = os.getenv(name)

    if value is None or not value.strip():
        return fallback

    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(
            f"{name}은 숫자여야 합니다. "
            f"actual={value!r}"
        ) from exc

    if parsed < 0:
        raise ValueError(
            f"{name}은 0 이상이어야 합니다. "
            f"actual={parsed}"
        )

    return parsed


def _read_bool_env(
    name: str,
    fallback: bool,
) -> bool:
    value = os.getenv(name)

    if value is None or not value.strip():
        return fallback

    normalized = value.strip().lower()

    if normalized in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }:
        return False

    raise ValueError(
        f"{name}은 boolean 값이어야 합니다. "
        f"actual={value!r}"
    )
