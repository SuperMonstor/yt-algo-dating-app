"""
Processing job status endpoint.
"""

import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn
from app.models import JobStatusResponse, JobProgress

router = APIRouter(tags=["status"])


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user),
):
    """Poll the status of a processing job."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT job_id, status, progress, error, created_at, updated_at
            FROM processing_jobs
            WHERE job_id = $1 AND user_id = $2
            """,
            job_id,
            user_id,
        )

    if not row:
        raise HTTPException(404, "Job not found")

    progress_data = json.loads(row["progress"]) if isinstance(row["progress"], str) else row["progress"]

    return JobStatusResponse(
        job_id=row["job_id"],
        status=row["status"],
        progress=JobProgress(**progress_data) if progress_data else JobProgress(),
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
