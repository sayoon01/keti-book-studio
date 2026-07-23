from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class GenerationRole(StrEnum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    WRITER = "writer"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    REVISER = "reviser"
    READER = "reader"
    FINALIZER = "finalizer"


@dataclass(frozen=True)
class RoleModelConfig:
    role: GenerationRole
    model: str
    temperature: float
    timeout_seconds: float


class ModelRouter:
    """
    Generation 역할별 모델 설정을 반환합니다.

    역할별 환경변수가 없으면 BOOK_STUDIO_MODEL을 사용합니다.
    따라서 처음에는 모든 역할이 같은 모델을 사용해도 되며,
    이후 환경변수만으로 Writer와 Reviewer 모델을 분리할 수 있습니다.
    """

    DEFAULT_MODEL = "gemma4-31b-32k:latest"
    DEFAULT_TIMEOUT_SECONDS = 600.0

    DEFAULT_TEMPERATURES: dict[
        GenerationRole,
        float,
    ] = {
        GenerationRole.PLANNER: 0.3,
        GenerationRole.RESEARCHER: 0.1,
        GenerationRole.WRITER: 0.5,
        GenerationRole.REVIEWER: 0.1,
        GenerationRole.EDITOR: 0.2,
        GenerationRole.REVISER: 0.35,
        GenerationRole.READER: 0.2,
        GenerationRole.FINALIZER: 0.25,
    }

    ENVIRONMENT_VARIABLES: dict[
        GenerationRole,
        str,
    ] = {
        GenerationRole.PLANNER: (
            "BOOK_STUDIO_PLANNER_MODEL"
        ),
        GenerationRole.RESEARCHER: (
            "BOOK_STUDIO_RESEARCHER_MODEL"
        ),
        GenerationRole.WRITER: (
            "BOOK_STUDIO_WRITER_MODEL"
        ),
        GenerationRole.REVIEWER: (
            "BOOK_STUDIO_REVIEWER_MODEL"
        ),
        GenerationRole.EDITOR: (
            "BOOK_STUDIO_EDITOR_MODEL"
        ),
        GenerationRole.REVISER: (
            "BOOK_STUDIO_REVISER_MODEL"
        ),
        GenerationRole.READER: (
            "BOOK_STUDIO_READER_MODEL"
        ),
        GenerationRole.FINALIZER: (
            "BOOK_STUDIO_FINALIZER_MODEL"
        ),
    }

    TEMPERATURE_VARIABLES: dict[
        GenerationRole,
        str,
    ] = {
        GenerationRole.PLANNER: (
            "BOOK_STUDIO_PLANNER_TEMPERATURE"
        ),
        GenerationRole.RESEARCHER: (
            "BOOK_STUDIO_RESEARCHER_TEMPERATURE"
        ),
        GenerationRole.WRITER: (
            "BOOK_STUDIO_WRITER_TEMPERATURE"
        ),
        GenerationRole.REVIEWER: (
            "BOOK_STUDIO_REVIEWER_TEMPERATURE"
        ),
        GenerationRole.EDITOR: (
            "BOOK_STUDIO_EDITOR_TEMPERATURE"
        ),
        GenerationRole.REVISER: (
            "BOOK_STUDIO_REVISER_TEMPERATURE"
        ),
        GenerationRole.READER: (
            "BOOK_STUDIO_READER_TEMPERATURE"
        ),
        GenerationRole.FINALIZER: (
            "BOOK_STUDIO_FINALIZER_TEMPERATURE"
        ),
    }

    def get_config(
        self,
        role: GenerationRole | str,
    ) -> RoleModelConfig:
        resolved_role = self._resolve_role(role)

        default_model = os.getenv(
            "BOOK_STUDIO_MODEL",
            self.DEFAULT_MODEL,
        ).strip()

        role_variable = self.ENVIRONMENT_VARIABLES[
            resolved_role
        ]

        model = os.getenv(
            role_variable,
            default_model,
        ).strip()

        if not model:
            raise ValueError(
                "LLM 모델명이 비어 있습니다. "
                f"role={resolved_role.value}, "
                f"environment_variable={role_variable}"
            )

        temperature = self._read_temperature(
            resolved_role
        )

        timeout_seconds = self._read_float(
            variable_name=(
                "OLLAMA_TIMEOUT_SECONDS"
            ),
            default=self.DEFAULT_TIMEOUT_SECONDS,
            minimum=1.0,
            maximum=3600.0,
        )

        return RoleModelConfig(
            role=resolved_role,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

    def get_all_configs(
        self,
    ) -> dict[GenerationRole, RoleModelConfig]:
        return {
            role: self.get_config(role)
            for role in GenerationRole
        }

    def _read_temperature(
        self,
        role: GenerationRole,
    ) -> float:
        role_variable = (
            self.TEMPERATURE_VARIABLES[role]
        )

        role_value = os.getenv(role_variable)

        if role_value is not None:
            return self._parse_float(
                variable_name=role_variable,
                raw_value=role_value,
                minimum=0.0,
                maximum=2.0,
            )

        common_value = os.getenv(
            "BOOK_STUDIO_TEMPERATURE"
        )

        if common_value is not None:
            return self._parse_float(
                variable_name=(
                    "BOOK_STUDIO_TEMPERATURE"
                ),
                raw_value=common_value,
                minimum=0.0,
                maximum=2.0,
            )

        return self.DEFAULT_TEMPERATURES[role]

    @staticmethod
    def _resolve_role(
        role: GenerationRole | str,
    ) -> GenerationRole:
        if isinstance(role, GenerationRole):
            return role

        try:
            return GenerationRole(
                str(role).strip().lower()
            )
        except ValueError as exc:
            valid_roles = ", ".join(
                item.value
                for item in GenerationRole
            )

            raise ValueError(
                f"지원하지 않는 Generation 역할입니다: {role}. "
                f"가능한 값: {valid_roles}"
            ) from exc

    def _read_float(
        self,
        *,
        variable_name: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        raw_value = os.getenv(variable_name)

        if raw_value is None:
            return default

        return self._parse_float(
            variable_name=variable_name,
            raw_value=raw_value,
            minimum=minimum,
            maximum=maximum,
        )

    @staticmethod
    def _parse_float(
        *,
        variable_name: str,
        raw_value: str,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"{variable_name}은 숫자여야 합니다: "
                f"{raw_value!r}"
            ) from exc

        if not minimum <= value <= maximum:
            raise ValueError(
                f"{variable_name}은 "
                f"{minimum} 이상 {maximum} 이하여야 합니다: "
                f"{value}"
            )

        return value
