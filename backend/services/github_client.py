"""GitHub 업로드 클라이언트.

Contents API로 파일을 생성/업데이트하고, 필요하면 저장소도 새로 만든다.
실제 HTTP 호출(http_get/http_post/http_put)은 인자로 주입받는다 —
테스트에서 진짜 GitHub API를 치지 않고 로직만 검증하기 위함.

주의: 저장소 생성은 토큰 소유자 개인 계정 기준(/user/repos)만 지원한다.
조직(organization) 소유 저장소 생성은 별도 엔드포인트(/orgs/{org}/repos)가
필요해 현재 범위에서는 지원하지 않는다.
"""

import base64
import os
from typing import Callable, Optional

import httpx

GITHUB_API_BASE = "https://api.github.com"

HttpGet = Callable[[str, dict], tuple[int, Optional[dict]]]
HttpPost = Callable[[str, dict, dict], tuple[int, Optional[dict]]]
HttpPut = Callable[[str, dict, dict], tuple[int, Optional[dict]]]


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN 환경변수가 설정되지 않았습니다. "
            "GitHub Personal Access Token을 발급받아(https://github.com/settings/tokens, "
            "'repo' 권한 필요) GITHUB_TOKEN 환경변수로 설정해주세요."
        )
    return token


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _default_http_get(url: str, headers: dict) -> tuple[int, Optional[dict]]:
    resp = httpx.get(url, headers=headers, timeout=30.0)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, None


def _default_http_post(url: str, headers: dict, json_body: dict) -> tuple[int, Optional[dict]]:
    resp = httpx.post(url, headers=headers, json=json_body, timeout=30.0)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, None


def _default_http_put(url: str, headers: dict, json_body: dict) -> tuple[int, Optional[dict]]:
    resp = httpx.put(url, headers=headers, json=json_body, timeout=30.0)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, None


def repo_exists(*, owner: str, repo: str, token: str, http_get: Optional[HttpGet] = None) -> bool:
    http_get = http_get or _default_http_get
    status, _ = http_get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", _auth_headers(token))
    return status == 200


def create_repo(
    *,
    name: str,
    private: bool = True,
    description: str = "",
    token: str,
    http_post: Optional[HttpPost] = None,
) -> dict:
    """토큰 소유자 계정 아래에 저장소를 만든다.

    이미 같은 이름의 저장소가 있으면 GitHub API가 422를 반환하는데,
    이 경우 에러로 취급하지 않고 {"already_exists": True}를 반환한다.
    """
    http_post = http_post or _default_http_post
    status, result = http_post(
        f"{GITHUB_API_BASE}/user/repos",
        _auth_headers(token),
        {"name": name, "private": private, "description": description, "auto_init": True},
    )
    if status == 422:
        return {"already_exists": True}
    if status not in (200, 201):
        raise RuntimeError(f"GitHub 저장소 생성 실패 (status={status}): {result}")
    return result or {}


def upload_file(
    *,
    owner: str,
    repo: str,
    path: str,
    content_bytes: bytes,
    message: str,
    branch: str = "main",
    token: str,
    http_get: Optional[HttpGet] = None,
    http_put: Optional[HttpPut] = None,
) -> dict:
    """path에 파일이 이미 있으면 sha를 조회해 덮어쓰고(업데이트 커밋), 없으면 새로 만든다."""
    http_get = http_get or _default_http_get
    http_put = http_put or _default_http_put

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    headers = _auth_headers(token)

    status, existing = http_get(f"{url}?ref={branch}", headers)
    sha = existing.get("sha") if status == 200 and existing else None

    body = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    status, result = http_put(url, headers, body)
    if status not in (200, 201):
        raise RuntimeError(f"GitHub 파일 업로드 실패 (status={status}): {result}")
    return result or {}
