"""Auth endpoints for email/password auth with optional code stubs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import UserModel
from ..schemas import (
    AuthFeatureResponse,
    AuthSignInRequest,
    AuthSignUpRequest,
    AuthTokenResponse,
    SendCodeRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _ensure_enabled() -> None:
    if not settings.auth_feature_enabled:
        raise HTTPException(status_code=503, detail="Auth is disabled.")


@router.get("/feature", response_model=AuthFeatureResponse)
def auth_feature() -> AuthFeatureResponse:
    return AuthFeatureResponse(enabled=settings.auth_feature_enabled)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def create_token(user: UserModel) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {"sub": user.id, "email": user.email, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserModel:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.split(" ", maxsplit=1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/send-code")
def send_login_code(payload: SendCodeRequest) -> dict[str, str]:
    _ensure_enabled()
    # TODO: implement email code delivery (SES/SendGrid). Stubbed for now.
    return {"message": f"Code not implemented for {payload.email}. Use password login."}


@router.post("/sign-in", response_model=AuthTokenResponse)
def sign_in(payload: AuthSignInRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    _ensure_enabled()
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password login only (codes not ready).")
    user = db.query(UserModel).filter(UserModel.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user)
    return AuthTokenResponse(
        token=token,
        user=UserResponse(
            user_id=user.id,
            username=user.username,
            rating_hint=user.rating_hint,
            exploit_default=user.exploit_default,
            share_data_opt_in=user.share_data_opt_in,
        ),
    )


@router.post("/sign-up", response_model=AuthTokenResponse)
def sign_up(payload: AuthSignUpRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    _ensure_enabled()
    email_normalized = payload.email.lower()
    existing = db.query(UserModel).filter(UserModel.email == email_normalized).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = UserModel(
        email=email_normalized,
        username=email_normalized.split("@", maxsplit=1)[0],
        password_hash=hash_password(payload.password),
        exploit_default="auto",
        share_data_opt_in=payload.remember,
        rating_hint=1800,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user)
    return AuthTokenResponse(
        token=token,
        user=UserResponse(
            user_id=user.id,
            username=user.username,
            rating_hint=user.rating_hint,
            exploit_default=user.exploit_default,
            share_data_opt_in=user.share_data_opt_in,
        ),
    )
