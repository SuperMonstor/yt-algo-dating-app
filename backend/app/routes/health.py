"""
Health check and stats endpoints (public, no auth).
"""

import time
from fastapi import APIRouter
from app.database import get_conn
from app.models import HealthResponse, StatsResponse

router = APIRouter(tags=["health"])

START_TIME = time.time()


@router.get("/health", response_model=HealthResponse)
async def health():
    db_status = "ok"
    try:
        async with get_conn() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        uptime_seconds=round(time.time() - START_TIME, 1),
    )


@router.get("/stats", response_model=StatsResponse)
async def stats():
    async with get_conn() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        active_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status = 'active'"
        )
        videos_cached = await conn.fetchval("SELECT COUNT(*) FROM video_metadata")
        channels_cached = await conn.fetchval("SELECT COUNT(*) FROM channel_metadata")
        videos_tagged = await conn.fetchval("SELECT COUNT(*) FROM video_tags")
        active_jobs = await conn.fetchval(
            "SELECT COUNT(*) FROM processing_jobs WHERE status NOT IN ('done', 'failed')"
        )

    return StatsResponse(
        users=users,
        active_users=active_users,
        videos_cached=videos_cached,
        channels_cached=channels_cached,
        videos_tagged=videos_tagged,
        active_jobs=active_jobs,
    )
