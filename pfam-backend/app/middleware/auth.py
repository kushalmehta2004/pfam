from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.config import get_settings


async def _fetch_jwks() -> list[dict[str, Any]]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(settings.clerk_jwks_url)
        response.raise_for_status()
        payload = response.json()
        keys = payload.get("keys", [])
        if not isinstance(keys, list):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_JWKS", "message": "Invalid JWKS response"},
            )
        return keys


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MISSING_AUTH_HEADER", "message": "Missing Authorization header"},
        )

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_AUTH_HEADER", "message": "Expected Bearer token"},
        )

    return authorization[len(prefix) :].strip()


async def verify_clerk_jwt(request: Request) -> Mapping[str, Any]:
    settings = get_settings()
    token = _extract_bearer_token(request.headers.get("Authorization"))

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "MISSING_KID", "message": "Token header missing kid"},
            )

        keys = await _fetch_jwks()
        matching_key = next((key for key in keys if key.get("kid") == kid), None)
        if matching_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNKNOWN_KID", "message": "Unable to find signing key"},
            )

        payload = jwt.decode(
            token,
            matching_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_aud": False},
        )

        org_id = payload.get("org_id")
        user_id = payload.get("sub")
        if not org_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CLAIMS", "message": "Missing org_id or user_id"},
            )

        request.state.org_id = org_id
        request.state.user_id = user_id
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token verification failed"},
        ) from exc

