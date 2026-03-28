"""
User profile endpoint (authenticated user's own profile).
"""

import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn
from app.models import ProfileResponse

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user_id: UUID = Depends(get_current_user)):
    """Get the authenticated user's profile summary."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT topic_weights, channel_weights, format_distribution,
                   domain_weights, total_long_form_videos, computed_at
            FROM user_profiles WHERE user_id = $1
            """,
            user_id,
        )

    if not row:
        raise HTTPException(404, "Profile not found. Upload your takeout first.")

    topic_weights = json.loads(row["topic_weights"]) if isinstance(row["topic_weights"], str) else row["topic_weights"]
    channel_weights = json.loads(row["channel_weights"]) if isinstance(row["channel_weights"], str) else row["channel_weights"]

    # Sort and take top 20
    top_topics = sorted(
        [{"topic": k, "weight": round(v, 3)} for k, v in topic_weights.items()],
        key=lambda x: x["weight"],
        reverse=True,
    )[:20]

    # Enrich channels with metadata
    channel_ids = list(channel_weights.keys())[:20]
    top_channels = []
    if channel_ids:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT channel_id, title, subscriber_count
                FROM channel_metadata
                WHERE channel_id = ANY($1)
                """,
                channel_ids,
            )
            meta_map = {r["channel_id"]: r for r in rows}

        sorted_channels = sorted(channel_weights.items(), key=lambda x: x[1], reverse=True)[:20]
        for ch_id, weight in sorted_channels:
            meta = meta_map.get(ch_id, {})
            top_channels.append({
                "channel_id": ch_id,
                "title": meta.get("title", "Unknown"),
                "weight": round(weight, 3),
                "subscriber_count": meta.get("subscriber_count", 0),
            })

    format_dist = json.loads(row["format_distribution"]) if isinstance(row["format_distribution"], str) else row["format_distribution"]
    domain_w = json.loads(row["domain_weights"]) if isinstance(row["domain_weights"], str) else row["domain_weights"]

    return ProfileResponse(
        user_id=user_id,
        top_topics=top_topics,
        top_channels=top_channels,
        format_distribution=format_dist or {},
        domain_weights=domain_w or {},
        total_long_form_videos=row["total_long_form_videos"] or 0,
        computed_at=row["computed_at"],
    )
