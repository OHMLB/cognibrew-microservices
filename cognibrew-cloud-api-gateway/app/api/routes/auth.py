"""
Auth routes — proxy to User Management Service.

Covers the CogniBrew barista journey:
  1. POST /auth/token          → login, get JWT
  2. POST /auth/user           → register new user
  3. GET  /auth/user           → list users (Admin) or self
  4. GET  /auth/user/{id}      → get specific user
  5. PATCH /auth/user/{id}     → partial update
  6. PUT   /auth/user/{id}     → full update
  7. DELETE /auth/user/{id}    → delete user

The gateway forwards the request body and Authorization header as-is.
JWT validation is handled entirely by the User Management Service.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import HttpClientDep, JWTDep
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_BASE = settings.USER_MANAGEMENT_SERVICE_URL


def _forward_headers(request: Request) -> dict:
    """Forward Authorization header from the incoming request."""
    headers = {}
    if auth := request.headers.get("Authorization"):
        headers["Authorization"] = auth
    return headers


async def _proxy(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    request: Request,
    body: dict | None = None,
) -> Response:
    """Generic proxy helper — forwards request to User Management Service."""
    url = f"{_BASE}{path}"
    headers = _forward_headers(request)
    try:
        resp = await client.request(method, url, json=body, headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        logger.error("User Management Service unreachable at %s", url)
        raise HTTPException(status_code=503, detail="User Management Service unavailable")
    except Exception as exc:
        logger.error("Proxy error for %s %s: %s", method, url, exc)
        raise HTTPException(status_code=502, detail="Bad gateway")


# ── Token (login) ─────────────────────────────────────────────────────────────

@router.post("/token", summary="Login — get JWT access token")
async def get_token(request: Request, client: HttpClientDep) -> Response:
    """Proxy POST /token to User Management Service.

    Request body: { "username": "<email>", "password": "<pwd>" }
    Response:     { "access_token": "...", "token_type": "Bearer", "expires_in": 7200 }
    """
    body = await request.json()
    return await _proxy(client, "POST", "/token", request, body)


# ── User CRUD ─────────────────────────────────────────────────────────────────

@router.post("/user", summary="Register a new user (barista / admin)")
async def create_user(request: Request, client: HttpClientDep) -> Response:
    """Proxy POST /user to User Management Service.

    Request body: { "name", "surname", "email", "role", "pwd" }
    No JWT required.
    """
    body = await request.json()
    return await _proxy(client, "POST", "/user", request, body)


@router.get("/user", summary="List all users (Admin) or current user")
async def get_users(request: Request, client: HttpClientDep, _: JWTDep) -> Response:
    """Proxy GET /user — requires JWT."""
    return await _proxy(client, "GET", "/user", request)


@router.get("/user/{user_id}", summary="Get a specific user by ID")
async def get_user(user_id: str, request: Request, client: HttpClientDep, _: JWTDep) -> Response:
    """Proxy GET /user/{id} — requires JWT. Admin or self only."""
    return await _proxy(client, "GET", f"/user/{user_id}", request)


@router.patch("/user/{user_id}", summary="Partial update of a user")
async def patch_user(user_id: str, request: Request, client: HttpClientDep, _: JWTDep) -> Response:
    """Proxy PATCH /user/{id} — requires JWT. Admin or self only."""
    body = await request.json()
    return await _proxy(client, "PATCH", f"/user/{user_id}", request, body)


@router.put("/user/{user_id}", summary="Full replacement of a user")
async def put_user(user_id: str, request: Request, client: HttpClientDep, _: JWTDep) -> Response:
    """Proxy PUT /user/{id} — requires JWT. Admin or self only."""
    body = await request.json()
    return await _proxy(client, "PUT", f"/user/{user_id}", request, body)


@router.delete("/user/{user_id}", summary="Delete a user")
async def delete_user(user_id: str, request: Request, client: HttpClientDep, _: JWTDep) -> Response:
    """Proxy DELETE /user/{id} — requires JWT. Admin or self only."""
    return await _proxy(client, "DELETE", f"/user/{user_id}", request)
