"""
Tests for the authenticated PDF content endpoint.

The PDF Viewer relies on `GET /api/v1/file-vault/{file_id}/content`
returning real PDF bytes owned by the caller, with proper Content-Type,
ownership checks, and 401/404 behavior. These tests cover the
authentication, ownership, and response-shape contract end-to-end.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services.auth import create_access_token
from app.services import storage as storage_service


OWNER_ID = "11111111-1111-1111-1111-111111111111"
FOREIGN_ID = "22222222-2222-2222-2222-222222222222"
FILE_ID = "33333333-3333-3333-3333-333333333333"


def _owned_file(extra: dict | None = None) -> SimpleNamespace:
    base = {
        "id": FILE_ID,
        "owner_id": OWNER_ID,
        "name": "lecture.pdf",
        "size_bytes": 1024,
        "mime_type": "application/pdf",
        "storage_key": f"users/{OWNER_ID}/vault/abc-lecture.pdf",
    }
    if extra:
        base.update(extra)
    return SimpleNamespace(**base)


def _foreign_file(extra: dict | None = None) -> SimpleNamespace:
    base = {
        "id": FILE_ID,
        "owner_id": FOREIGN_ID,
        "name": "private.pdf",
        "size_bytes": 1024,
        "mime_type": "application/pdf",
        "storage_key": f"users/{FOREIGN_ID}/vault/abc-private.pdf",
    }
    if extra:
        base.update(extra)
    return SimpleNamespace(**base)


class FakeSession:
    def __init__(self, file_obj):
        self._file = file_obj

    def get(self, _model, file_id):
        if self._file is None:
            return None
        if str(self._file.id) != str(file_id):
            return None
        return self._file


@pytest.fixture
def app_with_overrides():
    app.dependency_overrides = {}
    yield app
    app.dependency_overrides.clear()


def test_content_endpoint_requires_authentication(app_with_overrides) -> None:
    """No Authorization header → 401. The endpoint must never serve
    unauthenticated PDF bytes."""
    db = FakeSession(_owned_file())
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)

    with TestClient(app_with_overrides) as client:
        # Force dep resolution to behave like a public request (no overrides
        # for get_current_user). Easiest path: send no token.
        app_with_overrides.dependency_overrides.pop(get_current_user, None)
        response = client.get(f"/api/v1/file-vault/{FILE_ID}/content")
        assert response.status_code == 401


def test_content_endpoint_rejects_invalid_token(app_with_overrides) -> None:
    """A structurally invalid bearer must not leak the file."""
    db = FakeSession(_owned_file())
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert response.status_code == 401


def test_content_endpoint_serves_owned_pdf_bytes_with_application_pdf(app_with_overrides, monkeypatch) -> None:
    """An authenticated owner receives the actual PDF bytes with the
    canonical Content-Type — never a JSON / HTML / redirect envelope."""
    db = FakeSession(_owned_file())
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    pdf_bytes = b"%PDF-1.4\n%fake-but-valid-header\n%%EOF"

    def fake_stream(_user_id, _key, **_kwargs):
        # Return (content_length, status_code, iterator).
        return len(pdf_bytes), 200, iter([pdf_bytes])

    monkeypatch.setattr(storage_service, "stream_user_object", fake_stream)

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline;")
    assert "filename=" in response.headers["content-disposition"]
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == pdf_bytes


def test_content_endpoint_returns_404_for_foreign_file(app_with_overrides, monkeypatch) -> None:
    """A user must never be able to access another user's file, even if
    they know the file ID. The endpoint returns 404 (not 403) to prevent
    enumeration of foreign IDs."""
    db = FakeSession(_foreign_file())
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    called = False

    def unexpected_stream(*_args, **_kwargs):
        nonlocal called
        called = True
        return 0, 200, iter([])

    monkeypatch.setattr(storage_service, "stream_user_object", unexpected_stream)

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert called is False  # storage must never be reached for a foreign file


def test_content_endpoint_returns_404_for_missing_file(app_with_overrides, monkeypatch) -> None:
    """Missing file IDs return 404, not 200 with an empty body."""
    db = FakeSession(None)
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    called = False

    def unexpected_stream(*_args, **_kwargs):
        nonlocal called
        called = True
        return 0, 200, iter([])

    monkeypatch.setattr(storage_service, "stream_user_object", unexpected_stream)

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404
    assert called is False


def test_content_endpoint_supports_range_requests(app_with_overrides, monkeypatch) -> None:
    """PDF.js uses HTTP Range requests for partial document loading; the
    endpoint must honor `Range: bytes=A-B` and return 206 + Content-Range."""
    db = FakeSession(_owned_file())
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    pdf_bytes = b"%PDF-1.4\nabcdefghijklmnopqrstuvwxyz0123456789\n%%EOF"
    range_calls: list[tuple[int | None, int | None]] = []

    def fake_stream(_user_id, _key, **_kwargs):
        start = _kwargs.get("range_start")
        end = _kwargs.get("range_end")
        range_calls.append((start, end))
        if start is not None and end is not None:
            return len(pdf_bytes), 206, iter([pdf_bytes[start : end + 1]])
        return len(pdf_bytes), 200, iter([pdf_bytes])

    monkeypatch.setattr(storage_service, "stream_user_object", fake_stream)

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={
                "Authorization": f"Bearer {token}",
                "Range": "bytes=10-19",
            },
        )

    assert response.status_code == 206
    assert "content-range" in {key.lower() for key in response.headers.keys()}
    body = response.content
    # PDF.js expects a real subset of the bytes back.
    assert len(body) == 10
    assert body == pdf_bytes[10:20]
    # The endpoint must propagate the Range arguments to storage.
    assert range_calls[-1] == (10, 19)


def test_content_endpoint_rejects_non_pdf_mime(app_with_overrides) -> None:
    """Only PDF files are streamable through this endpoint."""
    db = FakeSession(
        _owned_file(
            {
                "mime_type": "image/png",
                "name": "screenshot.png",
            }
        )
    )
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 415


def test_content_endpoint_rejects_files_without_storage_key(app_with_overrides) -> None:
    """A row that was never actually uploaded must surface a clean 422,
    not crash or serve an empty body."""
    db = FakeSession(
        _owned_file({"storage_key": ""})
    )
    app_with_overrides.dependency_overrides[get_db] = _db_gen(db)
    app_with_overrides.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=OWNER_ID, role="student"
    )

    token = create_access_token(OWNER_ID, "student")
    with TestClient(app_with_overrides) as client:
        response = client.get(
            f"/api/v1/file-vault/{FILE_ID}/content",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 422


def test_storage_stream_rejects_keys_outside_user_namespace(monkeypatch) -> None:
    """Defense in depth: even if a bug let storage_key leak from the
    VaultFile row, the storage helper must refuse to read a key that
    doesn't begin with `users/{user_id}/`."""
    from app.services.storage import stream_user_object, StorageError

    with pytest.raises(StorageError):
        # Use a key that does NOT begin with the user namespace.
        list(stream_user_object(OWNER_ID, "some-other-user/abc.pdf")[2])


def _db_gen(db: FakeSession):
    """Build a FastAPI-compatible get_db override that yields one
    session then stops. FastAPI's dependency machinery iterates the
    override once and hands the yielded value to the route handler,
    matching the real `get_db` generator contract."""

    def _gen():
        yield db

    return _gen
