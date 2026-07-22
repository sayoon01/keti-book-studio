"""WorkspaceService 테스트."""

from backend.services.workspace_service import (
    WorkspaceService,
)


def test_workspace_contains_book_and_sources(
    session,
    prepared_book_with_source_collection,
):
    data = prepared_book_with_source_collection

    service = WorkspaceService(session)

    workspace = service.build_workspace(
        book_id=data["book_id"],
        include_full_text=False,
    )

    assert workspace.book.book_id == data["book_id"]
    assert workspace.book.automation_level == "BALANCED"

    assert (
        workspace.book_policy[
            "reader_test_policy"
        ]
        == "IMPORTANT_OR_FINAL"
    )

    assert (
        workspace.book_policy[
            "agent_communication"
        ]
        == "BLACKBOARD_ARTIFACT_MESSAGE"
    )


def test_workspace_normalizes_balanced_automation_level(
    session,
    prepared_book_with_source_collection,
):
    data = prepared_book_with_source_collection

    service = WorkspaceService(session)

    workspace = service.build_workspace(
        book_id=data["book_id"],
        include_full_text=False,
    )

    assert (
        workspace.book.automation_level
        == "BALANCED"
    )

    assert (
        workspace.book_policy["automation_level"]
        == "BALANCED"
    )
