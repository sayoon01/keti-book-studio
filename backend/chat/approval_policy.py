"""승인 필요 여부 판단.

BookConfig.approval_mode (safe/balanced/auto, Phase3에서 이미 존재)를 그대로 재사용한다.
- ask: 항상 승인 없이 즉시 답변 (아무것도 안 바꾸니까)
- generate_outline/approve_outline: 항상 승인 필요 (구조 변경/재생성은 되돌리기 부담이 큼)
- edit_config/edit_unit/generate_chapter: approval_mode 에 따라 달라짐
"""

ALWAYS_APPROVE = {"generate_outline", "approve_outline"}
NEVER_APPROVE = {"ask"}


def needs_approval(action: str, approval_mode: str) -> bool:
    if action in NEVER_APPROVE:
        return False
    if action in ALWAYS_APPROVE:
        return True

    if approval_mode == "safe":
        return True
    if approval_mode == "balanced":
        return action in {"edit_config", "edit_unit"}
    if approval_mode == "auto":
        return False
    return True
