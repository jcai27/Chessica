"""Auth endpoints (stubbed for email-based auth)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..schemas import (
    AuthFeatureResponse,
    AuthSignInRequest,
    AuthSignUpRequest,
    AuthTokenResponse,
    SendCodeRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_enabled() -> None:
    if not settings.auth_feature_enabled:
        raise HTTPException(status_code=503, detail="Auth is disabled.")


@router.get("/feature", response_model=AuthFeatureResponse)
def auth_feature() -> AuthFeatureResponse:
    return AuthFeatureResponse(enabled=settings.auth_feature_enabled)


@router.post("/send-code")
def send_login_code(payload: SendCodeRequest) -> dict[str, str]:
    _ensure_enabled()
    # In production, send a code via email (SES/SendGrid/etc.)
    return {"message": f"Code sent to {payload.email}"}


@router.post("/sign-in", response_model=AuthTokenResponse)
def sign_in(payload: AuthSignInRequest) -> AuthTokenResponse:
    _ensure_enabled()
    # TODO: validate code and issue JWT
    dummy_user = UserResponse(
        user_id=payload.email,
        username=payload.email.split("@", maxsplit=1)[0],
        rating_hint=1800,
        exploit_default="auto",
        share_data_opt_in=True,
    )
    return AuthTokenResponse(token="dev-auth-token", user=dummy_user)


@router.post("/sign-up", response_model=AuthTokenResponse)
def sign_up(payload: AuthSignUpRequest) -> AuthTokenResponse:
    _ensure_enabled()
    dummy_user = UserResponse(
        user_id=payload.email,
        username=payload.email.split("@", maxsplit=1)[0],
        rating_hint=1800,
        exploit_default="auto",
        share_data_opt_in=True,
    )
    return AuthTokenResponse(token="dev-auth-token", user=dummy_user)
