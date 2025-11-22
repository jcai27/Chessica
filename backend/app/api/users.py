"""User metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.auth import get_current_user, get_db
from ..models import UserModel
from ..schemas import PreferencesUpdateRequest, UserResponse

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", response_model=UserResponse)
def get_me(current_user: UserModel = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        user_id=current_user.id,
        username=current_user.username,
        rating_hint=current_user.rating_hint,
        exploit_default=current_user.exploit_default,
        share_data_opt_in=current_user.share_data_opt_in,
    )


@router.patch("/preferences", response_model=UserResponse)
def update_preferences(
    payload: PreferencesUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if payload.exploit_default:
        current_user.exploit_default = payload.exploit_default
    if payload.share_data_opt_in is not None:
        current_user.share_data_opt_in = payload.share_data_opt_in
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserResponse(
        user_id=current_user.id,
        username=current_user.username,
        rating_hint=current_user.rating_hint,
        exploit_default=current_user.exploit_default,
        share_data_opt_in=current_user.share_data_opt_in,
    )
