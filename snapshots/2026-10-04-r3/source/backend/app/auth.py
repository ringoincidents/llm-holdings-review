from __future__ import annotations

import os
import secrets

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


TOKEN_ENV = "LLM_HOLDINGS_API_TOKEN"
PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})
ROUTE_AUTH_PATHS = frozenset({
    "/clients/quantrade/ceo/proposal-outcomes/github-oidc",
    "/clients/quantrade/institutional-strategy-input/github-oidc",
})
MANAGED_CLOUD_ENV_KEYS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_PROJECT_ID",
)


def auth_enabled() -> bool:
    return bool((os.getenv(TOKEN_ENV) or "").strip())


def managed_cloud_detected() -> bool:
    return any((os.getenv(key) or "").strip() for key in MANAGED_CLOUD_ENV_KEYS)


def validate_auth_configuration() -> None:
    """Fail closed when deployed to managed cloud without the Runtime API token."""
    if managed_cloud_detected() and not auth_enabled():
        raise RuntimeError(
            f"{TOKEN_ENV} must be configured for managed-cloud Runtime deployment"
        )


def request_principal(request: Request) -> str:
    return str(getattr(request.state, "principal", "anonymous") or "anonymous")


def require_founder_principal(request: Request) -> str:
    principal = request_principal(request)
    if principal != "founder":
        raise HTTPException(status_code=403, detail="Founder principal required")
    return principal


class RuntimeBearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (
            request.method == "OPTIONS"
            or request.url.path in PUBLIC_PATHS
            or request.url.path in ROUTE_AUTH_PATHS
        ):
            request.state.principal = "anonymous"
            return await call_next(request)

        expected = (os.getenv(TOKEN_ENV) or "").strip()
        if not expected:
            if managed_cloud_detected():
                request.state.principal = "anonymous"
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Runtime authentication is not configured"},
                )
            # Trusted local/test fallback only. Managed-cloud deployment is fail-closed.
            request.state.principal = "founder"
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            request.state.principal = "anonymous"
            return JSONResponse(
                status_code=401,
                content={"detail": "Bearer authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not secrets.compare_digest(token, expected):
            request.state.principal = "anonymous"
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # The existing Runtime API token is the Founder control-plane credential.
        # Actor identity is server-owned; request payload fields cannot override it.
        request.state.principal = "founder"
        return await call_next(request)
