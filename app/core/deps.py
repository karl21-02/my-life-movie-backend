from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.services.access_token_service import (
    AccessTokenClaims,
    AccessTokenService,
    bearer_token_required_error,
)


_bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AccessTokenClaims:
    if credentials is None:
        raise bearer_token_required_error()
    return AccessTokenService(settings).verify(credentials.credentials)
