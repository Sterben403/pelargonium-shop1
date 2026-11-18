"""Minimal signed-token auth for the single owner account.

Token = base64(expiry timestamp) + "." + HMAC-SHA256 signature. Stateless, no extra deps.
"""
import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import Header, HTTPException, status

from . import config


def _sign(payload: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), config.ADMIN_PASSWORD.encode())


def issue_token() -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(hours=config.TOKEN_TTL_HOURS)
    payload = base64.urlsafe_b64encode(str(int(expires.timestamp())).encode()).decode()
    return f"{payload}.{_sign(payload)}", expires


def verify_token(token: str) -> bool:
    try:
        payload, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return False
        expires = int(base64.urlsafe_b64decode(payload.encode()).decode())
        return expires > datetime.now(UTC).timestamp()
    except (ValueError, UnicodeDecodeError):
        return False


def require_admin(authorization: str = Header(default="")) -> None:
    """FastAPI dependency: expects `Authorization: Bearer <token>`."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not verify_token(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthorized"},
                            headers={"WWW-Authenticate": "Bearer"})
