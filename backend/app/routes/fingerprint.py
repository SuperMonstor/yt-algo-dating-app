"""
Fingerprint endpoints.

GET /fingerprint         — authenticated user's own fingerprint
GET /fingerprint/{slug}  — public shareable fingerprint
"""

import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn
from app.services.embedder import compute_user_fingerprint

router = APIRouter(tags=["fingerprint"])


def generate_slug(user_id: UUID) -> str:
    """Deterministic short slug from user_id."""
    h = hashlib.sha256(str(user_id).encode()).hexdigest()[:10]
    return f"yt-{h}"


@router.get("/fingerprint")
async def get_own_fingerprint(user_id: UUID = Depends(get_current_user)):
    """Get the authenticated user's full fingerprint."""
    result = await compute_user_fingerprint(user_id)
    if not result:
        raise HTTPException(404, "Profile not found. Upload your takeout first.")
    result["slug"] = generate_slug(user_id)
    return result


@router.get("/fingerprint/{slug}")
async def get_public_fingerprint(slug: str):
    """Public shareable fingerprint. No auth required."""
    async with get_conn() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM users WHERE status = 'active'"
        )

    target_user_id = None
    for row in rows:
        if generate_slug(row["user_id"]) == slug:
            target_user_id = row["user_id"]
            break

    if not target_user_id:
        raise HTTPException(404, "Fingerprint not found")

    result = await compute_user_fingerprint(target_user_id)
    if not result:
        raise HTTPException(404, "Fingerprint not found")
    result["slug"] = slug
    return result
