from __future__ import annotations

from collections.abc import Callable
from typing import Any


# Workflow를 생성해서 반환하는 함수 타입입니다.
#
# Workflow마다 unit_id, book_id 같은 인자가 다를 수 있으므로
# **kwargs를 받을 수 있는 Callable로 정의합니다.
WorkflowFactory = Callable[..., Any]


class WorkflowRegistryError(Exception):
    """
    WorkflowRegistry 관련 기본 예외입니다.
    """


class WorkflowAlreadyRegisteredError(
    WorkflowRegistryError
):
    """
    동일한 workflow_type이 이미 등록되어 있을 때
    발생합니다.
    """


class WorkflowNotFoundError(
    WorkflowRegistryError,
    LookupError,
):
    """
    요청한 workflow_type이 등록되어 있지 않을 때
    발생합니다.
    """


class WorkflowRegistry:
    """
    Publishing Workflow 등록 및 조회 Registry입니다.

    ProductionEngine은 publishing.workflows 모듈을
    직접 참조하지 않고 이 Registry를 통해 실행할
    Workflow를 가져옵니다.

    예:
        registry.register(
            "chapter",
            build_chapter_workflow,
        )

        workflow = registry.build(
            "chapter",
            unit_id="unit-1",
        )
    """

    def __init__(self) -> None:
        self._factories: dict[
            str,
            WorkflowFactory,
        ] = {}

    def register(
        self,
        workflow_type: str,
        factory: WorkflowFactory,
        *,
        replace: bool = False,
    ) -> None:
        """
        Workflow factory를 등록합니다.

        Args:
            workflow_type:
                Workflow를 식별하는 문자열입니다.

            factory:
                Workflow 객체를 생성하는 함수입니다.

            replace:
                True이면 같은 이름의 기존 등록을
                덮어씁니다.

        Raises:
            ValueError:
                workflow_type이 비어 있거나 factory가
                호출 가능한 객체가 아닐 때 발생합니다.

            WorkflowAlreadyRegisteredError:
                동일한 이름이 이미 등록되어 있고
                replace=False일 때 발생합니다.
        """

        normalized_type = self._normalize(
            workflow_type
        )

        if not normalized_type:
            raise ValueError(
                "workflow_type은 비어 있을 수 없습니다."
            )

        if not callable(factory):
            raise ValueError(
                "Workflow factory는 호출 가능한 "
                "객체여야 합니다."
            )

        if (
            normalized_type in self._factories
            and not replace
        ):
            raise WorkflowAlreadyRegisteredError(
                "Workflow가 이미 등록되어 있습니다: "
                f"{workflow_type}"
            )

        self._factories[
            normalized_type
        ] = factory

    def unregister(
        self,
        workflow_type: str,
    ) -> None:
        """
        등록된 Workflow를 제거합니다.

        등록되어 있지 않은 Workflow를 제거하려 하면
        WorkflowNotFoundError가 발생합니다.
        """

        normalized_type = self._normalize(
            workflow_type
        )

        if normalized_type not in self._factories:
            raise WorkflowNotFoundError(
                "등록되지 않은 Workflow입니다: "
                f"{workflow_type}"
            )

        del self._factories[
            normalized_type
        ]

    def get_factory(
        self,
        workflow_type: str,
    ) -> WorkflowFactory:
        """
        Workflow factory를 반환합니다.
        """

        normalized_type = self._normalize(
            workflow_type
        )

        factory = self._factories.get(
            normalized_type
        )

        if factory is None:
            available = ", ".join(
                self.list_workflow_types()
            )

            if not available:
                available = "없음"

            raise WorkflowNotFoundError(
                "등록되지 않은 Workflow입니다: "
                f"{workflow_type}. "
                f"현재 등록된 Workflow: {available}"
            )

        return factory

    def build(
        self,
        workflow_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        등록된 factory를 실행해서 Workflow 객체를
        생성합니다.

        kwargs는 Workflow factory에 그대로 전달됩니다.
        """

        factory = self.get_factory(
            workflow_type
        )

        return factory(**kwargs)

    def contains(
        self,
        workflow_type: str,
    ) -> bool:
        """
        해당 Workflow가 등록되어 있는지 확인합니다.
        """

        normalized_type = self._normalize(
            workflow_type
        )

        return (
            normalized_type
            in self._factories
        )

    def list_workflow_types(
        self,
    ) -> list[str]:
        """
        등록된 Workflow 이름을 정렬해서 반환합니다.
        """

        return sorted(
            self._factories.keys()
        )

    def clear(self) -> None:
        """
        등록된 Workflow를 모두 제거합니다.

        주로 테스트에서 사용합니다.
        """

        self._factories.clear()

    def __len__(self) -> int:
        return len(
            self._factories
        )

    def __contains__(
        self,
        workflow_type: object,
    ) -> bool:
        if not isinstance(
            workflow_type,
            str,
        ):
            return False

        return self.contains(
            workflow_type
        )

    @staticmethod
    def _normalize(
        workflow_type: str,
    ) -> str:
        """
        Registry key를 정규화합니다.

        다음 값은 모두 동일하게 취급됩니다.

        - "chapter"
        - "CHAPTER"
        - " chapter "
        """

        return (
            str(workflow_type)
            .strip()
            .lower()
        )


def build_default_workflow_registry(
) -> WorkflowRegistry:
    """
    Book Studio에서 기본으로 사용하는 WorkflowRegistry를
    생성합니다.

    import를 함수 내부에서 수행해서 순환 import 가능성을
    줄입니다.
    """

    from backend.publishing.workflows import (
        build_chapter_workflow,
    )

    registry = WorkflowRegistry()

    registry.register(
        "chapter",
        build_chapter_workflow,
    )

    registry.register(
        "technical_chapter",
        build_chapter_workflow,
    )

    return registry
