"""
Supabase JWT authentication for FastAPI.

Validates JWTs issued by Supabase Auth (ES256). Extracts user_id (sub claim)
for use in protected endpoints.
"""

import json
import jwt
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import Settings, get_settings

security = HTTPBearer()

_public_key_cache = None


def _get_public_key(settings: Settings):
    """Convert the Supabase JWK to a public key for ES256 verification."""
    global _public_key_cache
    if _public_key_cache is not None:
        return _public_key_cache

    jwk_data = settings.supabase_jwk
    if not jwk_data:
        raise ValueError("SUPABASE_JWK not configured")

    if isinstance(jwk_data, str):
        jwk_data = json.loads(jwk_data)

    _public_key_cache = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk_data))
    return _public_key_cache


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> UUID:
    """Decode Supabase JWT and return user_id (sub claim)."""
    token = credentials.credentials
    try:
        public_key = _get_public_key(settings)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        user_id = UUID(payload["sub"])
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
