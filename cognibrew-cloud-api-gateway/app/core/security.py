"""
JWT verification for the API Gateway.

Validates the HS256 Bearer token issued by the User Management Service.
Uses the same secret / issuer / audience so tokens are accepted here
without an extra round-trip to the auth service.
"""

import logging

import jwt
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_jwt(request: Request) -> dict:
    """FastAPI dependency — extract and validate the JWT Bearer token.

    Returns the decoded claims dict on success.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _CREDENTIALS_EXCEPTION

    token = auth_header[len("Bearer "):]
    try:
        claims = jwt.decode(
            token,
            key=settings.JWT_SECRET_KEY,
            algorithms=settings.JWT_ALGORITHMS.split(","),
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        return claims
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise _CREDENTIALS_EXCEPTION
