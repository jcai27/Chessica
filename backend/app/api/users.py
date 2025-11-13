"""User metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import PreferencesUpdateRequest, UserResponse

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", response_model=UserResponse)
def get_me() -> UserResponse:
    return UserResponse(
        user_id="user_demo",
        username="demo",
        rating_hint=1800,
        exploit_default="auto",
        share_data_opt_in=True,
    )


@router.patch("/preferences", response_model=UserResponse)
def update_preferences(payload: PreferencesUpdateRequest) -> UserResponse:
    base = get_me()
    if payload.exploit_default:
        base.exploit_default = payload.exploit_default
    if payload.share_data_opt_in is not None:
        base.share_data_opt_in = payload.share_data_opt_in
    return base
