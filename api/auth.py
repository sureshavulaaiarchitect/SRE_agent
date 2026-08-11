import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from configs.config import settings

SECRET_KEY  = settings.JWT_SECRET
ALGORITHM   = "HS256"
EXPIRE_MINS = 60

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Credential store — extend to a DB-backed store for multi-user systems
# ---------------------------------------------------------------------------
_ROLE_MAP: dict[str, str] = {
    settings.ADMIN_USERNAME: "admin",
}

def _hash(value: str) -> str:
    """Deterministic PBKDF2-SHA256 hash using JWT_SECRET as salt."""
    return hashlib.pbkdf2_hmac(
        "sha256", value.encode(), settings.JWT_SECRET.encode(), 100_000
    ).hex()

def verify_credentials(username: str, password: str) -> Optional[str]:
    """
    Returns the role string on success, None on failure.
    - DEV_MODE with no ADMIN_PASSWORD: accepts any username, returns their
      configured role (or 'viewer' as fallback). Forces admin for the admin user.
    - Production: requires ADMIN_PASSWORD match; uses constant-time compare.
    """
    if settings.DEV_MODE and settings.ADMIN_PASSWORD is None:
        # Dev-only shortcut — no real secret checking
        return _ROLE_MAP.get(username, "viewer")

    if settings.ADMIN_PASSWORD is None:
        return None  # Production must always have a password configured

    # Constant-time comparison prevents timing attacks
    username_ok = secrets.compare_digest(
        _hash(username), _hash(settings.ADMIN_USERNAME)
    )
    password_ok = secrets.compare_digest(
        _hash(password), _hash(settings.ADMIN_PASSWORD)
    )
    if username_ok and password_ok:
        return _ROLE_MAP.get(username, "viewer")
    return None

def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MINS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    # DEV_MODE: bypass JWT validation
    if settings.DEV_MODE:
        return {"username": "dev", "role": "admin"}

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload["sub"], "role": payload.get("role", "viewer")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(*roles: str):
    def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _checker
