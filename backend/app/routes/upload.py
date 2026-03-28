"""
Takeout upload endpoints.

POST /upload    — first-time upload, creates user + job
POST /reupload  — additive merge for existing user
"""

from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from app.auth import get_current_user
from app.database import get_conn
from app.models import UploadResponse
from app.services.pipeline import run_pipeline

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_takeout(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user),
):
    """Upload takeout watch-history.html. Creates user if new, starts processing."""
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(400, "File must be a .html file (watch-history.html)")

    html_bytes = await file.read()
    if len(html_bytes) == 0:
        raise HTTPException(400, "File is empty")

    html_content = html_bytes.decode("utf-8", errors="replace")

    async with get_conn() as conn:
        # Create or update user
        await conn.execute(
            """
            INSERT INTO users (user_id, status, last_upload_at)
            VALUES ($1, 'processing', now())
            ON CONFLICT (user_id) DO UPDATE
            SET status = 'processing', last_upload_at = now(), updated_at = now()
            """,
            user_id,
        )

        # Create processing job
        job_id = await conn.fetchval(
            """
            INSERT INTO processing_jobs (user_id, status)
            VALUES ($1, 'queued')
            RETURNING job_id
            """,
            user_id,
        )

    background_tasks.add_task(run_pipeline, user_id, job_id, html_content, is_reupload=False)

    return UploadResponse(user_id=user_id, job_id=job_id)


@router.post("/reupload", response_model=UploadResponse)
async def reupload_takeout(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user),
):
    """Re-upload takeout for additive merge. User must already exist."""
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(400, "File must be a .html file (watch-history.html)")

    async with get_conn() as conn:
        existing = await conn.fetchval(
            "SELECT status FROM users WHERE user_id = $1", user_id
        )
        if not existing:
            raise HTTPException(404, "User not found. Use /upload for first-time upload.")

    html_bytes = await file.read()
    html_content = html_bytes.decode("utf-8", errors="replace")

    async with get_conn() as conn:
        await conn.execute(
            """
            UPDATE users SET status = 'processing', last_upload_at = now(), updated_at = now()
            WHERE user_id = $1
            """,
            user_id,
        )

        job_id = await conn.fetchval(
            """
            INSERT INTO processing_jobs (user_id, status)
            VALUES ($1, 'queued')
            RETURNING job_id
            """,
            user_id,
        )

    background_tasks.add_task(run_pipeline, user_id, job_id, html_content, is_reupload=True)

    return UploadResponse(user_id=user_id, job_id=job_id)
