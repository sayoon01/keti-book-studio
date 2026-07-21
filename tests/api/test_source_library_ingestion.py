from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.storage.models import SourceDocument, SourceProfile
from backend.storage.models_sources import SourceNode


def test_analyze_collection_creates_source_document(
    client: TestClient,
    session: Session,
):
    upload_response = client.post(
        "/api/source-library/collections/directory",
        data={
            "relative_paths": (
                "TestFolder/docs/guide.md"
            ),
            "collection_name": "테스트 자료",
            "root_name": "TestFolder",
        },
        files=[
            (
                "files",
                (
                    "guide.md",
                    BytesIO(
                        (
                            "# ADK Guide\n\n"
                            "Session과 Tool 설명"
                        ).encode("utf-8")
                    ),
                    "text/markdown",
                ),
            ),
        ],
    )

    assert upload_response.status_code == 201, (
        upload_response.text
    )

    collection_id = upload_response.json()[
        "collection"
    ]["id"]

    analyze_response = client.post(
        (
            "/api/source-library/collections/"
            f"{collection_id}/analyze"
        ),
        json={
            "workspace_id": "workspace-test",
            "book_id": None,
        },
    )

    assert analyze_response.status_code == 200, (
        analyze_response.text
    )

    body = analyze_response.json()

    assert body["collection_id"] == collection_id
    assert body["total_files"] == 1
    assert body["completed_files"] == 1
    assert body["skipped_files"] == 0
    assert body["failed_files"] == 0
    assert len(body["document_ids"]) == 1

    source_id = body["document_ids"][0]

    session.expire_all()

    document = session.get(
        SourceDocument,
        source_id,
    )

    assert document is not None
    assert document.source_id == source_id
    assert document.workspace_id == "workspace-test"
    assert document.source_type == "md"
    assert document.title == "guide"

    profile_statement = select(
        SourceProfile
    ).where(
        SourceProfile.source_id == source_id
    )

    profile = session.exec(
        profile_statement
    ).first()

    assert profile is not None
    assert profile.source_id == source_id

    node_statement = select(
        SourceNode
    ).where(
        SourceNode.document_id == source_id
    )

    node = session.exec(
        node_statement
    ).first()

    assert node is not None
    assert node.collection_id == collection_id
    assert node.relative_path == (
        "TestFolder/docs/guide.md"
    )
    assert node.status == "READY"
    assert node.document_id == source_id
