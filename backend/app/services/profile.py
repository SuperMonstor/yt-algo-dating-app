"""
Profile computation service.

Takes a user's video_watches + shared cache (video_tags, channel_metadata)
and computes the derived profile: topic_weights, channel_weights, domain_weights,
format_distribution, and embedding.

Everything here is recomputable — if we change the algorithm, just re-run for all users.
"""

import json
import math
import numpy as np
from uuid import UUID
from typing import Dict, List, Tuple
from sentence_transformers import SentenceTransformer

from app.database import get_conn

# Lazy-loaded model (first call downloads ~90MB, subsequent calls use cache)
_model = None


def _get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


async def compute_profile(user_id: UUID):
    """
    Compute the full derived profile for a user.

    Reads video_watches + video_tags + channel_metadata from the database,
    computes weights, generates embedding, and writes to user_profiles.
    Also updates the inverted indices (topic_user_index, channel_user_index).
    """
    async with get_conn() as conn:
        # Get user's watches joined with tags and metadata
        rows = await conn.fetch(
            """
            SELECT
                uvw.video_id,
                uvw.watch_count,
                vt.topics,
                vt.domain,
                vt.format,
                vm.channel_id,
                vm.view_count,
                cm.subscriber_count
            FROM user_video_watches uvw
            LEFT JOIN video_tags vt ON vt.video_id = uvw.video_id
            LEFT JOIN video_metadata vm ON vm.video_id = uvw.video_id
            LEFT JOIN channel_metadata cm ON cm.channel_id = vm.channel_id
            WHERE uvw.user_id = $1
            """,
            user_id,
        )

    if not rows:
        return

    # ── Compute topic weights ─────────────────────────────
    topic_weights = {}
    for row in rows:
        topics_raw = row["topics"]
        if not topics_raw:
            continue

        topics = json.loads(topics_raw) if isinstance(topics_raw, str) else topics_raw
        watch_count = row["watch_count"]

        for topic in topics:
            topic_weights[topic] = topic_weights.get(topic, 0) + watch_count

    # ── Compute channel weights ───────────────────────────
    # Weight = watch_count × niche_score (log scale of inverse subscriber count)
    channel_weights = {}
    channel_watch_counts = {}
    max_subs = 1

    for row in rows:
        ch_id = row["channel_id"]
        if not ch_id:
            continue
        subs = row["subscriber_count"] or 1
        max_subs = max(max_subs, subs)
        channel_watch_counts[ch_id] = channel_watch_counts.get(ch_id, 0) + row["watch_count"]

    for row in rows:
        ch_id = row["channel_id"]
        if not ch_id or ch_id in channel_weights:
            continue
        subs = row["subscriber_count"] or 1
        niche_score = math.log(max(max_subs, 1_000_000) / max(subs, 1))
        channel_weights[ch_id] = channel_watch_counts.get(ch_id, 1) * niche_score

    # ── Compute domain weights ────────────────────────────
    domain_weights = {}
    for row in rows:
        domain = row["domain"]
        if not domain:
            continue
        watch_count = row["watch_count"]
        domain_weights[domain] = domain_weights.get(domain, 0) + watch_count

    # ── Compute format distribution ───────────────────────
    format_counts = {}
    total_format = 0
    for row in rows:
        fmt = row["format"]
        if not fmt:
            continue
        watch_count = row["watch_count"]
        format_counts[fmt] = format_counts.get(fmt, 0) + watch_count
        total_format += watch_count

    format_distribution = {}
    if total_format > 0:
        for fmt, count in format_counts.items():
            format_distribution[fmt] = round(count / total_format, 4)

    # ── Compute embedding ─────────────────────────────────
    # Weighted average of topic embeddings
    embedding = _compute_embedding(topic_weights)

    # ── Write profile to DB ───────────────────────────────
    total_videos = sum(row["watch_count"] for row in rows)

    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO user_profiles (
                user_id, topic_weights, channel_weights,
                format_distribution, domain_weights,
                embedding, total_long_form_videos, computed_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, now())
            ON CONFLICT (user_id) DO UPDATE SET
                topic_weights = $2, channel_weights = $3,
                format_distribution = $4, domain_weights = $5,
                embedding = $6, total_long_form_videos = $7,
                computed_at = now()
            """,
            user_id,
            json.dumps(topic_weights),
            json.dumps(channel_weights),
            json.dumps(format_distribution),
            json.dumps(domain_weights),
            _embedding_to_pgvector(embedding),
            total_videos,
        )

        # ── Update inverted indices ───────────────────────
        # Clear old entries for this user
        await conn.execute("DELETE FROM topic_user_index WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM channel_user_index WHERE user_id = $1", user_id)

        # Insert topic index entries
        if topic_weights:
            await conn.executemany(
                "INSERT INTO topic_user_index (topic, user_id, weight) VALUES ($1, $2, $3)",
                [(topic, user_id, weight) for topic, weight in topic_weights.items()],
            )

        # Insert channel index entries
        if channel_weights:
            await conn.executemany(
                "INSERT INTO channel_user_index (channel_id, user_id, weight) VALUES ($1, $2, $3)",
                [(ch_id, user_id, weight) for ch_id, weight in channel_weights.items()],
            )

    return {
        "topic_count": len(topic_weights),
        "channel_count": len(channel_weights),
        "domain_count": len(domain_weights),
        "format_count": len(format_distribution),
        "total_videos": total_videos,
    }


def _compute_embedding(topic_weights: Dict[str, float]) -> np.ndarray:
    """Compute user embedding as weighted average of topic embeddings."""
    if not topic_weights:
        return np.zeros(384, dtype=np.float32)

    model = _get_embedding_model()
    topics = list(topic_weights.keys())
    weights = np.array([topic_weights[t] for t in topics], dtype=np.float32)

    # Normalize weights to sum to 1
    weight_sum = weights.sum()
    if weight_sum > 0:
        weights = weights / weight_sum

    # Encode all topics at once (batched, efficient)
    topic_embeddings = model.encode(topics, show_progress_bar=False)

    # Weighted average
    user_embedding = np.average(topic_embeddings, axis=0, weights=weights)

    # L2 normalize for cosine similarity
    norm = np.linalg.norm(user_embedding)
    if norm > 0:
        user_embedding = user_embedding / norm

    return user_embedding.astype(np.float32)


def _embedding_to_pgvector(embedding: np.ndarray) -> str:
    """Convert numpy array to pgvector string format."""
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"
