from typing import Optional
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.logging import log_event

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

async def verify_api_key(
    request: Request,
    header_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> bool:
    """
    Validates service-to-service authentication.
    If settings.service_api_key is configured:
      Checks X-API-Key header or Authorization: Bearer token.
    If settings.service_api_key is None or empty:
      Allows transparent unauthenticated access (local development mode).
    """
    configured_key = settings.service_api_key
    if not configured_key or not configured_key.strip():
        # Open access in local development mode
        return True

    provided_key = None
    if header_key:
        provided_key = header_key.strip()
    elif bearer_creds and bearer_creds.credentials:
        provided_key = bearer_creds.credentials.strip()

    if not provided_key or provided_key != configured_key:
        log_event(
            "ERROR",
            f"Unauthorized request to {request.method} {request.url.path} from client {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing API key. Provide via 'X-API-Key' or 'Authorization: Bearer <key>'."
        )

    return True

