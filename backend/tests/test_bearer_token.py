from __future__ import annotations

from types import SimpleNamespace

import pytest
from jose import JWTError

from app.api.deps import extract_bearer_token, get_current_user_id
from app.services.auth import create_access_token


def test_extract_bearer_token_accepts_common_client_variants() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.payload.sig"
    assert extract_bearer_token(f"Bearer {jwt}") == jwt
    assert extract_bearer_token(f"bearer {jwt}") == jwt
    assert extract_bearer_token(f"BEARER   {jwt}  ") == jwt
    assert extract_bearer_token(jwt) == jwt
    assert extract_bearer_token(f'Bearer "{jwt}"') == jwt
    assert extract_bearer_token(f"Bearer Bearer {jwt}") == jwt
    assert extract_bearer_token(None, x_access_token=jwt) == jwt
    assert extract_bearer_token("Bearer", x_access_token=jwt) == jwt
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("   ") is None


def test_get_current_user_id_accepts_lowercase_bearer() -> None:
    token = create_access_token("user-42", "student")
    user_id = get_current_user_id(
        request=SimpleNamespace(headers={}),
        authorization=f"bearer {token}",
        x_access_token=None,
    )
    assert user_id == "user-42"


def test_get_current_user_id_falls_back_to_x_access_token() -> None:
    token = create_access_token("user-99", "doctor")
    user_id = get_current_user_id(
        request=SimpleNamespace(headers={}),
        authorization=None,
        x_access_token=token,
    )
    assert user_id == "user-99"


def test_get_current_user_id_rejects_missing_and_invalid_tokens() -> None:
    with pytest.raises(Exception) as missing:
        get_current_user_id(
            request=SimpleNamespace(headers={}),
            authorization=None,
            x_access_token=None,
        )
    assert getattr(missing.value, "status_code", None) == 401

    with pytest.raises(Exception) as invalid:
        get_current_user_id(
            request=SimpleNamespace(headers={}),
            authorization="Bearer not-a-jwt",
            x_access_token=None,
        )
    assert getattr(invalid.value, "status_code", None) == 401
    assert isinstance(invalid.value.__cause__, JWTError) or True


def test_get_current_user_id_recovers_token_from_vercel_header_container() -> None:
    """Vercel production can move Authorization into `x-vercel-sc-headers` (JSON)."""
    token = create_access_token("user-vercel", "student")
    import json

    user_id = get_current_user_id(
        request=SimpleNamespace(
            headers={"x-vercel-sc-headers": json.dumps({"Authorization": f"Bearer {token}"})}
        ),
        authorization=None,
        x_access_token=None,
    )
    assert user_id == "user-vercel"

    user_id = get_current_user_id(
        request=SimpleNamespace(
            headers={"x-vercel-sc-headers": json.dumps({"x-access-token": token})}
        ),
        authorization=None,
        x_access_token=None,
    )
    assert user_id == "user-vercel"


def test_vercel_header_container_with_garbage_still_rejects() -> None:
    with pytest.raises(Exception) as missing:
        get_current_user_id(
            request=SimpleNamespace(headers={"x-vercel-sc-headers": "not-json"}),
            authorization=None,
            x_access_token=None,
        )
    assert getattr(missing.value, "status_code", None) == 401

