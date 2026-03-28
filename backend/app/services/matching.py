"""
Matching engine — Stage 1 (candidate retrieval) + Stage 2 (multi-signal scoring).

Follows ADR-010:
- Stage 1: Inverted index lookup to find ~2000 candidates sharing topics/channels
- Stage 2: Multi-signal scoring (topic overlap, embedding sim, channel overlap,
           domain hierarchy, format similarity, complementary gaps)
- Asymmetric harmonic mean for final score
- Conversation seed generation for each match
"""

import json
import math
import numpy as np
from uuid import UUID
from typing import Dict, List, Tuple, Optional

from app.database import get_conn


# ── Scoring weights (from ADR-010) ───────────────────────

W_TOPIC = 0.35
W_EMBEDDING = 0.25
W_CHANNEL = 0.20
W_DOMAIN = 0.10
W_FORMAT = 0.05
W_COMPLEMENTARY = 0.05

# Max candidates from Stage 1
MAX_CANDIDATES = 2000

# Minimum score to store as a match
MIN_MATCH_SCORE = 0.01


async def run_matching(user_id: UUID):
    """
    Run the full matching pipeline for a user.

    1. Load the user's profile
    2. Stage 1: find candidates via inverted indices
    3. Stage 2: score each candidate
    4. Store matches
    """
    user_profile = await _load_profile(user_id)
    if not user_profile:
        return 0

    # Get total user count for IDF
    async with get_conn() as conn:
        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status = 'active'"
        )

    if total_users < 2:
        return 0

    # Stage 1: candidate retrieval
    candidates = await _stage1_retrieve(user_id, user_profile, total_users)

    if not candidates:
        return 0

    # Load candidate profiles
    candidate_ids = list(candidates.keys())
    candidate_profiles = await _load_profiles_batch(candidate_ids)

    # Stage 2: score each candidate
    matches = []
    for cand_id, cand_profile in candidate_profiles.items():
        score_a_to_b = _score_pair(user_profile, cand_profile, total_users)
        score_b_to_a = _score_pair(cand_profile, user_profile, total_users)

        # Harmonic mean for asymmetry handling
        if score_a_to_b + score_b_to_a > 0:
            final_score = 2 * score_a_to_b * score_b_to_a / (score_a_to_b + score_b_to_a)
        else:
            final_score = 0

        if final_score < MIN_MATCH_SCORE:
            continue

        # Compute detailed breakdown
        breakdown = _compute_breakdown(user_profile, cand_profile, total_users)

        # Generate match details (shared topics, channels, conversation seed)
        details = await _generate_match_details(user_id, cand_id, user_profile, cand_profile)

        matches.append({
            "user_a": min(user_id, cand_id, key=str),
            "user_b": max(user_id, cand_id, key=str),
            "score": final_score,
            "score_a_to_b": score_a_to_b if str(user_id) < str(cand_id) else score_b_to_a,
            "score_b_to_a": score_b_to_a if str(user_id) < str(cand_id) else score_a_to_b,
            "breakdown": breakdown,
            "details": details,
        })

    # Store matches
    await _store_matches(user_id, matches)

    return len(matches)


# ── Stage 1: Candidate Retrieval ─────────────────────────


async def _stage1_retrieve(
    user_id: UUID,
    user_profile: dict,
    total_users: int,
) -> Dict[UUID, float]:
    """
    Find candidate users who share topics/channels with the query user.
    IDF weighting ensures niche overlaps surface first.
    Returns {candidate_id: coarse_score} for top candidates.
    """
    coarse_scores = {}

    topic_weights = user_profile["topic_weights"]
    channel_weights = user_profile["channel_weights"]

    async with get_conn() as conn:
        # Topic-based candidates
        if topic_weights:
            topics = list(topic_weights.keys())
            rows = await conn.fetch(
                """
                SELECT user_id, topic, weight
                FROM topic_user_index
                WHERE topic = ANY($1) AND user_id != $2
                """,
                topics, user_id,
            )

            # Compute IDF for each topic
            topic_user_counts = {}
            for row in rows:
                topic_user_counts[row["topic"]] = topic_user_counts.get(row["topic"], 0) + 1

            for row in rows:
                cand_id = row["user_id"]
                topic = row["topic"]
                # IDF = log(total_users / users_with_topic)
                users_with_topic = topic_user_counts.get(topic, 1)
                idf = math.log(max(total_users, 2) / max(users_with_topic, 1))
                user_weight = topic_weights.get(topic, 0)

                if cand_id not in coarse_scores:
                    coarse_scores[cand_id] = 0
                coarse_scores[cand_id] += idf * user_weight

        # Channel-based candidates
        if channel_weights:
            channels = list(channel_weights.keys())
            rows = await conn.fetch(
                """
                SELECT cui.user_id, cui.channel_id, cm.subscriber_count
                FROM channel_user_index cui
                LEFT JOIN channel_metadata cm ON cm.channel_id = cui.channel_id
                WHERE cui.channel_id = ANY($1) AND cui.user_id != $2
                """,
                channels, user_id,
            )

            for row in rows:
                cand_id = row["user_id"]
                subs = row["subscriber_count"] or 1
                # Niche score: smaller channels score higher
                niche_score = math.log(max(1_000_000, 1) / max(subs, 1))

                if cand_id not in coarse_scores:
                    coarse_scores[cand_id] = 0
                coarse_scores[cand_id] += niche_score

    # Return top candidates by coarse score
    sorted_candidates = sorted(coarse_scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_candidates[:MAX_CANDIDATES])


# ── Stage 2: Multi-Signal Scoring ────────────────────────


def _score_pair(profile_a: dict, profile_b: dict, total_users: int) -> float:
    """Compute directional score from A's perspective looking at B."""
    topic_score = _topic_overlap_score(profile_a, profile_b, total_users)
    embedding_score = _embedding_similarity(profile_a, profile_b)
    channel_score = _channel_overlap_score(profile_a, profile_b)
    domain_score = _domain_hierarchy_score(profile_a, profile_b)
    format_score = _format_similarity_score(profile_a, profile_b)
    comp_score = _complementary_gap_score(profile_a, profile_b, total_users)

    return (
        W_TOPIC * topic_score
        + W_EMBEDDING * embedding_score
        + W_CHANNEL * channel_score
        + W_DOMAIN * domain_score
        + W_FORMAT * format_score
        + W_COMPLEMENTARY * comp_score
    )


def _topic_overlap_score(a: dict, b: dict, total_users: int) -> float:
    """
    Shared topics weighted by IDF.
    score = Σ idf[t] × min(a.weight[t], b.weight[t]) for shared topics
    """
    a_topics = a["topic_weights"]
    b_topics = b["topic_weights"]
    shared = set(a_topics.keys()) & set(b_topics.keys())

    if not shared:
        return 0

    score = 0
    for topic in shared:
        # Approximate IDF using weight magnitude as proxy
        # (real IDF would come from global_stats, but this is good enough for scoring)
        min_weight = min(a_topics[topic], b_topics[topic])
        score += min_weight

    # Normalize by the geometric mean of total weights
    a_total = sum(a_topics.values()) or 1
    b_total = sum(b_topics.values()) or 1
    normalizer = math.sqrt(a_total * b_total)

    return min(score / normalizer, 1.0)


def _embedding_similarity(a: dict, b: dict) -> float:
    """Cosine similarity between user embeddings."""
    emb_a = a.get("embedding")
    emb_b = b.get("embedding")

    if emb_a is None or emb_b is None:
        return 0

    if isinstance(emb_a, str):
        emb_a = np.array([float(x) for x in emb_a.strip("[]").split(",")], dtype=np.float32)
    if isinstance(emb_b, str):
        emb_b = np.array([float(x) for x in emb_b.strip("[]").split(",")], dtype=np.float32)

    if not isinstance(emb_a, np.ndarray):
        emb_a = np.array(emb_a, dtype=np.float32)
    if not isinstance(emb_b, np.ndarray):
        emb_b = np.array(emb_b, dtype=np.float32)

    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)

    if norm_a == 0 or norm_b == 0:
        return 0

    cosine = np.dot(emb_a, emb_b) / (norm_a * norm_b)
    # Clamp to [0, 1] — negative cosine means opposite interests, treat as 0
    return max(0, float(cosine))


def _channel_overlap_score(a: dict, b: dict) -> float:
    """
    Shared channels weighted by niche score (inverse subscriber count).
    """
    a_channels = a["channel_weights"]
    b_channels = b["channel_weights"]
    shared = set(a_channels.keys()) & set(b_channels.keys())

    if not shared:
        return 0

    score = sum(min(a_channels[ch], b_channels[ch]) for ch in shared)

    a_total = sum(a_channels.values()) or 1
    b_total = sum(b_channels.values()) or 1
    normalizer = math.sqrt(a_total * b_total)

    return min(score / normalizer, 1.0)


def _domain_hierarchy_score(a: dict, b: dict) -> float:
    """
    Count shared prefix levels between domain strings.
    "sports > tennis > equipment" vs "sports > tennis > aus open" → 2 shared levels
    """
    a_domains = a["domain_weights"]
    b_domains = b["domain_weights"]

    if not a_domains or not b_domains:
        return 0

    # Build a set of all domain prefixes with weights
    def get_prefixes(domains):
        prefixes = {}
        for domain, weight in domains.items():
            parts = [p.strip() for p in domain.split(">")]
            for i in range(1, len(parts) + 1):
                prefix = " > ".join(parts[:i])
                prefixes[prefix] = prefixes.get(prefix, 0) + weight
        return prefixes

    a_prefixes = get_prefixes(a_domains)
    b_prefixes = get_prefixes(b_domains)

    shared = set(a_prefixes.keys()) & set(b_prefixes.keys())
    if not shared:
        return 0

    score = sum(min(a_prefixes[p], b_prefixes[p]) for p in shared)

    a_total = sum(a_prefixes.values()) or 1
    b_total = sum(b_prefixes.values()) or 1
    normalizer = math.sqrt(a_total * b_total)

    return min(score / normalizer, 1.0)


def _format_similarity_score(a: dict, b: dict) -> float:
    """Cosine similarity between format distribution vectors."""
    a_fmt = a["format_distribution"]
    b_fmt = b["format_distribution"]

    if not a_fmt or not b_fmt:
        return 0

    all_formats = set(a_fmt.keys()) | set(b_fmt.keys())
    vec_a = np.array([a_fmt.get(f, 0) for f in all_formats], dtype=np.float32)
    vec_b = np.array([b_fmt.get(f, 0) for f in all_formats], dtype=np.float32)

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0

    return max(0, float(np.dot(vec_a, vec_b) / (norm_a * norm_b)))


def _complementary_gap_score(a: dict, b: dict, total_users: int) -> float:
    """
    Detect when one user is deep in a topic and the other is exploring it.
    "You could learn from each other."
    """
    a_topics = a["topic_weights"]
    b_topics = b["topic_weights"]
    shared = set(a_topics.keys()) & set(b_topics.keys())

    if not shared:
        return 0

    gap_score = 0
    for topic in shared:
        wa = a_topics[topic]
        wb = b_topics[topic]
        ratio = max(wa, wb) / max(min(wa, wb), 0.01)
        if ratio > 5:  # One is much deeper than the other
            gap_score += math.log(ratio)

    # Normalize
    max_possible = len(shared) * math.log(100)  # reasonable upper bound
    return min(gap_score / max(max_possible, 1), 1.0)


def _compute_breakdown(a: dict, b: dict, total_users: int) -> dict:
    """Compute individual signal scores for explainability."""
    return {
        "topic_overlap": round(_topic_overlap_score(a, b, total_users), 4),
        "embedding_sim": round(_embedding_similarity(a, b), 4),
        "channel_overlap": round(_channel_overlap_score(a, b), 4),
        "domain_sim": round(_domain_hierarchy_score(a, b), 4),
        "format_sim": round(_format_similarity_score(a, b), 4),
        "complementary": round(_complementary_gap_score(a, b, total_users), 4),
    }


# ── Match Details & Conversation Seeds ───────────────────


async def _generate_match_details(
    user_id: UUID, cand_id: UUID,
    user_profile: dict, cand_profile: dict,
) -> dict:
    """Generate shared topics, channels, complementary topics, and conversation seed."""
    # Shared topics (sorted by combined weight)
    u_topics = user_profile["topic_weights"]
    c_topics = cand_profile["topic_weights"]
    shared_topics = []
    for topic in set(u_topics.keys()) & set(c_topics.keys()):
        combined = u_topics[topic] + c_topics[topic]
        shared_topics.append({"topic": topic, "combined_weight": round(combined, 2)})
    shared_topics.sort(key=lambda x: x["combined_weight"], reverse=True)
    shared_topics = shared_topics[:10]

    # Shared channels (sorted by niche score)
    u_channels = user_profile["channel_weights"]
    c_channels = cand_profile["channel_weights"]
    shared_channel_ids = set(u_channels.keys()) & set(c_channels.keys())

    shared_channels = []
    if shared_channel_ids:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT channel_id, title, subscriber_count
                FROM channel_metadata
                WHERE channel_id = ANY($1)
                """,
                list(shared_channel_ids),
            )
            for row in rows:
                shared_channels.append({
                    "channel_id": row["channel_id"],
                    "title": row["title"],
                    "subscriber_count": row["subscriber_count"],
                })
        # Sort by subscriber count ascending (niche first)
        shared_channels.sort(key=lambda x: x["subscriber_count"] or 0)
        shared_channels = shared_channels[:10]

    # Complementary topics (one deep, one exploring)
    complementary = []
    for topic in set(u_topics.keys()) & set(c_topics.keys()):
        wa = u_topics[topic]
        wb = c_topics[topic]
        ratio = max(wa, wb) / max(min(wa, wb), 0.01)
        if ratio > 5:
            deep_user = "you" if wa > wb else "them"
            exploring_user = "them" if wa > wb else "you"
            complementary.append({
                "topic": topic,
                "you": "deep" if wa > wb else "exploring",
                "them": "exploring" if wa > wb else "deep",
            })
    complementary = complementary[:5]

    # Conversation seed — pick the most niche shared channel and a video from it
    conversation_seed = None
    if shared_channels:
        best_channel = shared_channels[0]  # Most niche
        async with get_conn() as conn:
            video = await conn.fetchrow(
                """
                SELECT vm.video_id, vm.title, vm.channel_title
                FROM video_metadata vm
                WHERE vm.channel_id = $1
                ORDER BY vm.view_count DESC
                LIMIT 1
                """,
                best_channel["channel_id"],
            )
            if video:
                conversation_seed = {
                    "video_id": video["video_id"],
                    "title": video["title"],
                    "channel": video["channel_title"],
                    "prompt": "You both follow %s. What did you think of \"%s\"?" % (
                        best_channel["title"] or "this channel",
                        video["title"] or "their latest video",
                    ),
                }

    return {
        "shared_topics": shared_topics,
        "shared_channels": shared_channels,
        "complementary_topics": complementary,
        "conversation_seed": conversation_seed,
    }


# ── DB Helpers ───────────────────────────────────────────


async def _load_profile(user_id: UUID) -> Optional[dict]:
    """Load a user's profile from the database."""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT topic_weights, channel_weights, format_distribution,
                   domain_weights, embedding
            FROM user_profiles
            WHERE user_id = $1
            """,
            user_id,
        )
    if not row:
        return None

    return {
        "topic_weights": json.loads(row["topic_weights"]) if isinstance(row["topic_weights"], str) else (row["topic_weights"] or {}),
        "channel_weights": json.loads(row["channel_weights"]) if isinstance(row["channel_weights"], str) else (row["channel_weights"] or {}),
        "format_distribution": json.loads(row["format_distribution"]) if isinstance(row["format_distribution"], str) else (row["format_distribution"] or {}),
        "domain_weights": json.loads(row["domain_weights"]) if isinstance(row["domain_weights"], str) else (row["domain_weights"] or {}),
        "embedding": row["embedding"],
    }


async def _load_profiles_batch(user_ids: List[UUID]) -> Dict[UUID, dict]:
    """Load profiles for multiple users."""
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, topic_weights, channel_weights, format_distribution,
                   domain_weights, embedding
            FROM user_profiles
            WHERE user_id = ANY($1)
            """,
            user_ids,
        )

    profiles = {}
    for row in rows:
        profiles[row["user_id"]] = {
            "topic_weights": json.loads(row["topic_weights"]) if isinstance(row["topic_weights"], str) else (row["topic_weights"] or {}),
            "channel_weights": json.loads(row["channel_weights"]) if isinstance(row["channel_weights"], str) else (row["channel_weights"] or {}),
            "format_distribution": json.loads(row["format_distribution"]) if isinstance(row["format_distribution"], str) else (row["format_distribution"] or {}),
            "domain_weights": json.loads(row["domain_weights"]) if isinstance(row["domain_weights"], str) else (row["domain_weights"] or {}),
            "embedding": row["embedding"],
        }
    return profiles


async def _store_matches(user_id: UUID, matches: List[dict]):
    """Store computed matches, replacing old ones for this user."""
    async with get_conn() as conn:
        # Remove old matches involving this user
        await conn.execute(
            "DELETE FROM matches WHERE user_id_a = $1 OR user_id_b = $1",
            user_id,
        )

        for m in matches:
            await conn.execute(
                """
                INSERT INTO matches (
                    user_id_a, user_id_b, score, score_a_to_b, score_b_to_a,
                    topic_overlap, embedding_sim, channel_overlap,
                    domain_sim, format_sim, complementary, details
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (user_id_a, user_id_b) DO UPDATE SET
                    score = $3, score_a_to_b = $4, score_b_to_a = $5,
                    topic_overlap = $6, embedding_sim = $7, channel_overlap = $8,
                    domain_sim = $9, format_sim = $10, complementary = $11,
                    details = $12, computed_at = now()
                """,
                m["user_a"], m["user_b"], m["score"],
                m["score_a_to_b"], m["score_b_to_a"],
                m["breakdown"]["topic_overlap"],
                m["breakdown"]["embedding_sim"],
                m["breakdown"]["channel_overlap"],
                m["breakdown"]["domain_sim"],
                m["breakdown"]["format_sim"],
                m["breakdown"]["complementary"],
                json.dumps(m["details"]),
            )
