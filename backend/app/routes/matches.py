"""
Matches endpoint.
"""

import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn
from app.models import MatchResponse, MatchListResponse

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=MatchListResponse)
async def get_matches(user_id: UUID = Depends(get_current_user)):
    """Get all matches for the authenticated user, ranked by score."""
    async with get_conn() as conn:
        # Check user exists and is active
        status = await conn.fetchval(
            "SELECT status FROM users WHERE user_id = $1", user_id
        )
        if not status:
            raise HTTPException(404, "User not found")
        if status != "active":
            raise HTTPException(400, f"User status is '{status}'. Matches available when status is 'active'.")

        rows = await conn.fetch(
            """
            SELECT
                CASE WHEN user_id_a = $1 THEN user_id_b ELSE user_id_a END as match_user_id,
                score, score_a_to_b, score_b_to_a,
                topic_overlap, embedding_sim, channel_overlap,
                domain_sim, format_sim, complementary,
                details
            FROM matches
            WHERE user_id_a = $1 OR user_id_b = $1
            ORDER BY score DESC
            """,
            user_id,
        )

    matches = []
    for row in rows:
        details = json.loads(row["details"]) if isinstance(row["details"], str) else (row["details"] or {})
        matches.append(MatchResponse(
            match_user_id=row["match_user_id"],
            score=round(row["score"], 4),
            score_breakdown={
                "topic_overlap": round(row["topic_overlap"] or 0, 4),
                "embedding_similarity": round(row["embedding_sim"] or 0, 4),
                "channel_overlap": round(row["channel_overlap"] or 0, 4),
                "domain_similarity": round(row["domain_sim"] or 0, 4),
                "format_similarity": round(row["format_sim"] or 0, 4),
                "complementary_gaps": round(row["complementary"] or 0, 4),
            },
            shared_topics=details.get("shared_topics", []),
            shared_channels=details.get("shared_channels", []),
            complementary_topics=details.get("complementary_topics", []),
            conversation_seed=details.get("conversation_seed"),
        ))

    return MatchListResponse(
        user_id=user_id,
        matches=matches,
        total=len(matches),
    )
