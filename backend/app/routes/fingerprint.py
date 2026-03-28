"""
Fingerprint endpoints.

GET /fingerprint         — authenticated user's own fingerprint
GET /fingerprint/{slug}  — public shareable fingerprint
"""

import json
import math
import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_conn
from app.models import FingerprintResponse

router = APIRouter(tags=["fingerprint"])


def generate_slug(user_id: UUID) -> str:
    """Deterministic short slug from user_id."""
    h = hashlib.sha256(str(user_id).encode()).hexdigest()[:10]
    return f"yt-{h}"


def classify_personality(
    format_distribution: dict,
    topic_weights: dict,
    domain_weights: dict,
) -> dict:
    """Derive a personality type from viewing patterns."""
    unique_topics = len(topic_weights)

    # Count distinct top-level domains
    top_domains = set()
    for domain in domain_weights:
        top_level = domain.split(" > ")[0] if " > " in domain else domain
        top_domains.add(top_level)

    podcast_pct = format_distribution.get("podcast", 0) + format_distribution.get("interview", 0)
    tutorial_pct = format_distribution.get("tutorial", 0) + format_distribution.get("explainer", 0)

    # Compute topic concentration (how focused vs spread)
    if topic_weights:
        weights = sorted(topic_weights.values(), reverse=True)
        top_10_weight = sum(weights[:10])
        total_weight = sum(weights)
        concentration = top_10_weight / total_weight if total_weight > 0 else 0
    else:
        concentration = 0

    # Classification rules (first match wins)
    if podcast_pct > 0.5:
        return {
            "label": "Podcast Brain",
            "description": "You consume most of your content through long-form conversations and interviews. You like depth, nuance, and hearing experts think out loud.",
        }
    if concentration > 0.7 and unique_topics < 30:
        return {
            "label": "Deep Diver",
            "description": "You go deep on a few topics rather than skimming many. When something catches your interest, you watch everything about it.",
        }
    if len(top_domains) >= 4 and unique_topics > 80:
        return {
            "label": "Polymath",
            "description": "Your interests span multiple domains — from tech to philosophy to sports. You're the person who connects ideas across fields.",
        }
    if tutorial_pct > 0.4:
        return {
            "label": "Visual Learner",
            "description": "You learn by watching. Tutorials, explainers, and how-tos dominate your feed. YouTube is your classroom.",
        }

    # Check niche depth — would need channel data, approximate from topic count
    culture_domains = {"music", "film", "art", "literature", "culture", "entertainment"}
    culture_weight = sum(
        w for d, w in domain_weights.items()
        if d.split(" > ")[0].lower() in culture_domains
    )
    total_domain_weight = sum(domain_weights.values()) if domain_weights else 1
    if culture_weight / total_domain_weight > 0.4:
        return {
            "label": "Culture Vulture",
            "description": "Music, film, art, and culture dominate your watch history. You have strong taste and you know it.",
        }

    return {
        "label": "Niche Explorer",
        "description": "You seek out content most people never find. Small channels, obscure topics — your feed is uniquely yours.",
    }


async def build_fingerprint(user_id: UUID) -> dict:
    """Build the full fingerprint for a user."""
    async with get_conn() as conn:
        profile = await conn.fetchrow(
            """
            SELECT topic_weights, channel_weights, format_distribution,
                   domain_weights, total_long_form_videos, computed_at
            FROM user_profiles WHERE user_id = $1
            """,
            user_id,
        )
        if not profile:
            return None

        topic_weights = json.loads(profile["topic_weights"]) if isinstance(profile["topic_weights"], str) else profile["topic_weights"]
        channel_weights = json.loads(profile["channel_weights"]) if isinstance(profile["channel_weights"], str) else profile["channel_weights"]
        format_dist = json.loads(profile["format_distribution"]) if isinstance(profile["format_distribution"], str) else profile["format_distribution"]
        domain_weights = json.loads(profile["domain_weights"]) if isinstance(profile["domain_weights"], str) else profile["domain_weights"]

        # Top topics
        top_topics = sorted(
            [{"topic": k, "weight": round(v, 3)} for k, v in topic_weights.items()],
            key=lambda x: x["weight"],
            reverse=True,
        )[:15]

        # Top channels with metadata
        sorted_channels = sorted(channel_weights.items(), key=lambda x: x[1], reverse=True)
        channel_ids = [ch_id for ch_id, _ in sorted_channels[:15]]

        channel_meta = {}
        if channel_ids:
            rows = await conn.fetch(
                """
                SELECT channel_id, title, subscriber_count, video_count
                FROM channel_metadata WHERE channel_id = ANY($1)
                """,
                channel_ids,
            )
            channel_meta = {r["channel_id"]: r for r in rows}

        top_channels = []
        for ch_id, weight in sorted_channels[:15]:
            meta = channel_meta.get(ch_id, {})
            top_channels.append({
                "channel_id": ch_id,
                "title": meta.get("title", "Unknown"),
                "weight": round(weight, 3),
                "subscriber_count": meta.get("subscriber_count", 0),
            })

        # Most niche channels (lowest subscriber count that user actually watches)
        all_channel_ids = [ch_id for ch_id, _ in sorted_channels]
        niche_channels = []
        if all_channel_ids:
            rows = await conn.fetch(
                """
                SELECT channel_id, title, subscriber_count
                FROM channel_metadata
                WHERE channel_id = ANY($1) AND subscriber_count > 0
                ORDER BY subscriber_count ASC
                LIMIT 10
                """,
                all_channel_ids,
            )
            niche_channels = [
                {
                    "channel_id": r["channel_id"],
                    "title": r["title"],
                    "subscriber_count": r["subscriber_count"],
                }
                for r in rows
            ]

        # Most niche videos
        niche_videos = []
        video_rows = await conn.fetch(
            """
            SELECT vm.video_id, vm.title, vm.channel_title, vm.view_count
            FROM user_video_watches uvw
            JOIN video_metadata vm ON vm.video_id = uvw.video_id
            WHERE uvw.user_id = $1 AND vm.view_count > 0
            ORDER BY vm.view_count ASC
            LIMIT 10
            """,
            user_id,
        )
        niche_videos = [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "channel": r["channel_title"],
                "view_count": r["view_count"],
            }
            for r in video_rows
        ]

        # Watch stats
        watch_stats_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_videos,
                COUNT(DISTINCT vm.channel_id) as unique_channels,
                COALESCE(SUM(vm.duration_seconds * uvw.watch_count), 0) as total_seconds
            FROM user_video_watches uvw
            JOIN video_metadata vm ON vm.video_id = uvw.video_id
            WHERE uvw.user_id = $1
            """,
            user_id,
        )

        total_seconds = watch_stats_row["total_seconds"] or 0
        watch_stats = {
            "total_videos": watch_stats_row["total_videos"],
            "unique_channels": watch_stats_row["unique_channels"],
            "estimated_hours": round(total_seconds / 3600, 1),
        }

        # Domain distribution (top-level domains, normalized)
        domain_total = sum(domain_weights.values()) if domain_weights else 1
        domain_distribution = {}
        for domain, weight in domain_weights.items():
            top_level = domain.split(" > ")[0] if " > " in domain else domain
            domain_distribution[top_level] = domain_distribution.get(top_level, 0) + weight
        # Normalize to percentages
        for k in domain_distribution:
            domain_distribution[k] = round(domain_distribution[k] / domain_total * 100, 1)
        # Sort by value descending
        domain_distribution = dict(
            sorted(domain_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        personality = classify_personality(format_dist or {}, topic_weights or {}, domain_weights or {})

        return {
            "user_id": user_id,
            "slug": generate_slug(user_id),
            "top_topics": top_topics,
            "top_channels": top_channels,
            "format_distribution": format_dist or {},
            "domain_distribution": domain_distribution,
            "watch_stats": watch_stats,
            "most_niche_channels": niche_channels,
            "most_niche_videos": niche_videos,
            "personality_type": personality,
            "computed_at": profile["computed_at"],
        }


@router.get("/fingerprint", response_model=FingerprintResponse)
async def get_own_fingerprint(user_id: UUID = Depends(get_current_user)):
    """Get the authenticated user's full fingerprint."""
    result = await build_fingerprint(user_id)
    if not result:
        raise HTTPException(404, "Profile not found. Upload your takeout first.")
    return FingerprintResponse(**result)


@router.get("/fingerprint/{slug}", response_model=FingerprintResponse)
async def get_public_fingerprint(slug: str):
    """Public shareable fingerprint. No auth required."""
    # Find user by slug (slug is derived from user_id, so we search all active users)
    async with get_conn() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM users WHERE status = 'active'"
        )

    # Find matching slug
    target_user_id = None
    for row in rows:
        if generate_slug(row["user_id"]) == slug:
            target_user_id = row["user_id"]
            break

    if not target_user_id:
        raise HTTPException(404, "Fingerprint not found")

    result = await build_fingerprint(target_user_id)
    if not result:
        raise HTTPException(404, "Fingerprint not found")
    return FingerprintResponse(**result)
