"""Postmark email helpers for verification."""

from __future__ import annotations

import httpx

from .config import settings


def send_verification_email(email: str, token: str) -> None:
    if not settings.postmark_api_token or not settings.email_from:
        return
    verify_url = f"{settings.verification_url_base}?token={token}"
    payload = {
        "From": settings.email_from,
        "To": email,
        "Subject": "Verify your Chessica account",
        "TextBody": f"Click to verify your account: {verify_url}",
        "HtmlBody": f"<p>Click to verify your account: <a href='{verify_url}'>{verify_url}</a></p>",
    }
    try:
        httpx.post(
            "https://api.postmarkapp.com/email",
            json=payload,
            headers={"X-Postmark-Server-Token": settings.postmark_api_token},
            timeout=4.0,
        )
    except Exception:
        # Fail silently; verification can be retried.
        pass
