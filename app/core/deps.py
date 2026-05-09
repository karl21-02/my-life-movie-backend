from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.services.access_token_service import (
    AccessTokenClaims,
    AccessTokenService,
    bearer_token_required_error,
)


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise bearer_token_required_error()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise bearer_token_required_error()
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AccessTokenClaims:
    token = _extract_bearer_token(authorization)
    return AccessTokenService(settings).verify(token)
