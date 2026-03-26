"""
User management endpoint.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn

router = APIRouter(tags=["user"])


@router.delete("/user")
async def delete_user(user_id: UUID = Depends(get_current_user)):
    """
    Full account deletion.

    Removes: user record, video watches, profile, index entries, matches, jobs.
    All tables use ON DELETE CASCADE from the users FK, so deleting the user
    cascades to all related data.
    """
    async with get_conn() as conn:
        existing = await conn.fetchval(
            "SELECT user_id FROM users WHERE user_id = $1", user_id
        )
        if not existing:
            raise HTTPException(404, "User not found")

        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

    return {"status": "deleted", "user_id": str(user_id)}
