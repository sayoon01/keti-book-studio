"""Phase 9 완료 조건 테스트 (실제 GitHub API는 치지 않고, HTTP 호출을 주입해서 로직만 검증).

1. github_client.upload_file: 파일이 이미 있으면 sha를 포함해서 PUT (업데이트),
   없으면 sha 없이 PUT (신규 생성)
2. github_client.create_repo: 이미 존재(422)하면 에러 아니라 already_exists=True로 처리
3. GITHUB_TOKEN 없으면 export/github 호출 시 500 + 안내 메시지
4. export/github 엔드포인트가 실제로 파일을 만들고, upload_file에 올바른 인자를 넘기는지
5. 파일 경로 미지정 시 책 제목을 slug화해서 사용하는지
"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

os.environ["KETI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KETI_UPLOAD_DIR"] = tempfile.mkdtemp()
os.environ["KETI_PERSONA_DIR"] = tempfile.mkdtemp()
os.environ["KETI_EXPORT_DIR"] = tempfile.mkdtemp()

from backend.main import app  # noqa: E402
from backend.services import github_client  # noqa: E402
from backend.storage.database import engine  # noqa: E402
from backend.storage.persona_seed import seed_system_personas  # noqa: E402


def test_upload_file_includes_sha_when_file_exists():
    calls = {"get": None, "put": None}

    def fake_get(url, headers):
        calls["get"] = url
        return 200, {"sha": "existing-sha-123"}

    def fake_put(url, headers, json_body):
        calls["put"] = json_body
        return 200, {"content": {"path": "book.md"}, "commit": {"sha": "new-commit-sha"}}

    result = github_client.upload_file(
        owner="alice",
        repo="my-books",
        path="book.md",
        content_bytes=b"hello",
        message="update",
        token="fake-token",
        http_get=fake_get,
        http_put=fake_put,
    )

    assert calls["put"]["sha"] == "existing-sha-123"
    assert result["commit"]["sha"] == "new-commit-sha"


def test_upload_file_omits_sha_when_file_is_new():
    def fake_get(url, headers):
        return 404, None

    def fake_put(url, headers, json_body):
        return 201, {"content": {"path": "book.md"}, "commit": {"sha": "first-commit-sha"}}

    calls = {}

    def spy_put(url, headers, json_body):
        calls["body"] = json_body
        return fake_put(url, headers, json_body)

    github_client.upload_file(
        owner="alice",
        repo="my-books",
        path="book.md",
        content_bytes=b"hello",
        message="create",
        token="fake-token",
        http_get=fake_get,
        http_put=spy_put,
    )

    assert "sha" not in calls["body"]


def test_upload_file_raises_on_failure_status():
    def fake_get(url, headers):
        return 404, None

    def fake_put(url, headers, json_body):
        return 403, {"message": "Forbidden"}

    with pytest.raises(RuntimeError, match="업로드 실패"):
        github_client.upload_file(
            owner="alice",
            repo="my-books",
            path="book.md",
            content_bytes=b"hello",
            message="create",
            token="fake-token",
            http_get=fake_get,
            http_put=fake_put,
        )


def test_create_repo_treats_422_as_already_exists():
    def fake_post(url, headers, json_body):
        return 422, {"message": "name already exists"}

    result = github_client.create_repo(name="my-books", token="fake-token", http_post=fake_post)
    assert result == {"already_exists": True}


def test_create_repo_raises_on_other_errors():
    def fake_post(url, headers, json_body):
        return 401, {"message": "Bad credentials"}

    with pytest.raises(RuntimeError, match="생성 실패"):
        github_client.create_repo(name="my-books", token="fake-token", http_post=fake_post)


def _fake_research_llm(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({"summary": "요약", "main_topics": [], "key_findings": [],
                        "tables": [], "limitations": [], "recommended_uses": []})


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_system_personas(session)
    yield
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_book_with_unit(client) -> dict:
    book = client.post("/api/books", json={"workspace_id": "ws-1", "title": "ALD 공정 기술서!"}).json()
    outline = client.get(f"/api/books/{book['book_id']}/outline").json()["outline"]
    client.post(
        f"/api/outlines/{outline['outline_id']}/units",
        json={"title": "1장. 개요", "target_characters": 1000},
    )
    return book


def test_export_github_fails_without_token(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    book = _create_book_with_unit(client)

    resp = client.post(
        f"/api/books/{book['book_id']}/export/github",
        json={"format": "markdown", "repo_owner": "alice", "repo_name": "my-books"},
    )
    assert resp.status_code == 500
    assert "GITHUB_TOKEN" in resp.json()["detail"]


def test_export_github_uses_slugified_title_as_default_path(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    book = _create_book_with_unit(client)

    captured = {}

    def fake_upload_file(**kwargs):
        captured.update(kwargs)
        return {"commit": {"sha": "abc123"}}

    monkeypatch.setattr("backend.api.exports.upload_file", fake_upload_file)

    resp = client.post(
        f"/api/books/{book['book_id']}/export/github",
        json={"format": "markdown", "repo_owner": "alice", "repo_name": "my-books"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert captured["owner"] == "alice"
    assert captured["repo"] == "my-books"
    assert captured["path"] == "ald-공정-기술서.md"
    assert captured["branch"] == "main"
    assert body["commit_sha"] == "abc123"
    assert body["github_url"].endswith("ald-공정-기술서.md")


def test_export_github_creates_repo_when_requested(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    book = _create_book_with_unit(client)

    create_repo_calls = []
    monkeypatch.setattr(
        "backend.api.exports.create_repo",
        lambda **kwargs: create_repo_calls.append(kwargs) or {"already_exists": False},
    )
    monkeypatch.setattr(
        "backend.api.exports.upload_file", lambda **kwargs: {"commit": {"sha": "x"}}
    )

    resp = client.post(
        f"/api/books/{book['book_id']}/export/github",
        json={
            "format": "markdown",
            "repo_owner": "alice",
            "repo_name": "new-repo",
            "create_repo": True,
            "private": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert len(create_repo_calls) == 1
    assert create_repo_calls[0]["name"] == "new-repo"
    assert create_repo_calls[0]["private"] is False


def test_export_github_respects_custom_path_and_message(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    book = _create_book_with_unit(client)

    captured = {}
    monkeypatch.setattr(
        "backend.api.exports.upload_file",
        lambda **kwargs: captured.update(kwargs) or {"commit": {"sha": "x"}},
    )

    client.post(
        f"/api/books/{book['book_id']}/export/github",
        json={
            "format": "docx",
            "repo_owner": "alice",
            "repo_name": "my-books",
            "path": "docs/final.docx",
            "commit_message": "책 완성본 업로드",
        },
    )

    assert captured["path"] == "docs/final.docx"
    assert captured["message"] == "책 완성본 업로드"
