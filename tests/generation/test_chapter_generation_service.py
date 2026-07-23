from __future__ import annotations

from unittest.mock import Mock

from backend.generation.chapter_generation_service import (
    ChapterGenerationService,
)
from backend.generation.model_router import (
    ModelRouter,
)


def test_chapter_generation_service_can_be_created():
    service = ChapterGenerationService()

    assert service is not None


def test_chapter_generation_service_accepts_dependencies():
    client = Mock()
    router = ModelRouter()

    try:
        service = ChapterGenerationService(
            client=client,
            model_router=router,
        )
    except TypeError:
        # 아직 생성자 주입을 적용하지 않았다면
        # 해당 코드 적용 전에는 이 테스트가 실패합니다.
        raise AssertionError(
            "ChapterGenerationService 생성자에 "
            "client와 model_router 주입을 추가하세요."
        )

    assert service is not None
    assert service._client is client
    assert service._model_router is router
