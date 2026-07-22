"""
Deprecated compatibility module.

새 코드는 `backend.orchestration.agent_schemas`을 사용해야 합니다.
이 파일은 기존 import가 즉시 깨지지 않도록 임시로 유지합니다.
"""

from backend.orchestration.agent_schemas import *  # noqa: F401,F403
