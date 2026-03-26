"""Tests for profile computation service."""

import json
import pytest
from uuid import UUID
from tests.conftest import (
    seed_user, seed_video_metadata, seed_video_tags, seed_watches,
    TEST_USER_ID,
)
from app.services.profile import compute_profile, _compute_embedding, _embedding_to_pgvector


# ── Unit tests ───────────────────────────────────────────


def test_compute_embedding_returns_384_dims():
    topics = {"machine learning": 3.5, "startups": 2.1, "philosophy": 1.8}
    emb = _compute_embedding(topics)
    assert emb.shape == (384,)
    # Should be normalized (L2 norm ~= 1)
    import numpy as np
    norm = np.linalg.norm(emb)
    assert abs(norm - 1.0) < 0.01


def test_compute_embedding_empty_topics():
    emb = _compute_embedding({})
    assert emb.shape == (384,)
    import numpy as np
    assert np.allclose(emb, 0)


def test_embedding_to_pgvector_format():
    import numpy as np
    emb = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = _embedding_to_pgvector(emb)
    assert result.startswith("[")
    assert result.endswith("]")
    assert "0.1" in result


# ── Integration tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_compute_profile_full(pool):
    """Test full profile computation from watches + tags."""
    await seed_user(pool)

    # Seed 3 videos across 2 channels with tags
    await seed_video_metadata(pool, "vid_001", "ch_ai", "Intro to Transformers",
                               view_count=50000, subscriber_count=10000)
    await seed_video_metadata(pool, "vid_002", "ch_ai", "Advanced NLP",
                               view_count=30000, subscriber_count=10000)
    await seed_video_metadata(pool, "vid_003", "ch_biz", "Startup Fundraising",
                               view_count=80000, subscriber_count=500000)

    await seed_video_tags(pool, "vid_001",
                          topics=["transformers", "machine learning", "AI"],
                          domain="tech > AI > NLP", fmt="tutorial")
    await seed_video_tags(pool, "vid_002",
                          topics=["NLP", "machine learning", "deep learning"],
                          domain="tech > AI > NLP", fmt="tutorial")
    await seed_video_tags(pool, "vid_003",
                          topics=["fundraising", "startups", "venture capital"],
                          domain="business > startups", fmt="podcast")

    # User watched vid_001 3 times, vid_002 twice, vid_003 once
    await seed_watches(pool, TEST_USER_ID, {
        "vid_001": 3, "vid_002": 2, "vid_003": 1,
    })

    result = await compute_profile(TEST_USER_ID)

    assert result is not None
    assert result["topic_count"] > 0
    assert result["channel_count"] == 2
    assert result["domain_count"] > 0
    assert result["format_count"] > 0
    assert result["total_videos"] == 6  # 3 + 2 + 1

    # Verify profile was written to DB
    async with pool.acquire() as conn:
        profile = await conn.fetchrow(
            "SELECT * FROM user_profiles WHERE user_id = $1", TEST_USER_ID
        )
        assert profile is not None

        topic_weights = json.loads(profile["topic_weights"])
        assert "machine learning" in topic_weights
        # ML appears in vid_001 (3 watches) + vid_002 (2 watches) = 5
        assert topic_weights["machine learning"] == 5

        channel_weights = json.loads(profile["channel_weights"])
        assert "ch_ai" in channel_weights
        assert "ch_biz" in channel_weights
        # ch_ai is smaller (10K subs) so should have higher niche-weighted score
        assert channel_weights["ch_ai"] > channel_weights["ch_biz"]

        format_dist = json.loads(profile["format_distribution"])
        # 5 tutorial watches (vid_001 + vid_002), 1 podcast (vid_003)
        assert format_dist["tutorial"] > format_dist["podcast"]
        # Should sum to ~1.0
        total = sum(format_dist.values())
        assert abs(total - 1.0) < 0.01

        # Embedding should exist and be 384-dim pgvector
        assert profile["embedding"] is not None


@pytest.mark.asyncio
async def test_compute_profile_updates_inverted_indices(pool):
    """Profile computation should populate topic_user_index and channel_user_index."""
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001", "ch_001", subscriber_count=5000)
    await seed_video_tags(pool, "vid_001", topics=["machine learning", "AI"])
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 2})

    await compute_profile(TEST_USER_ID)

    async with pool.acquire() as conn:
        topic_entries = await conn.fetch(
            "SELECT * FROM topic_user_index WHERE user_id = $1", TEST_USER_ID
        )
        assert len(topic_entries) == 2  # "machine learning" and "AI"

        channel_entries = await conn.fetch(
            "SELECT * FROM channel_user_index WHERE user_id = $1", TEST_USER_ID
        )
        assert len(channel_entries) == 1  # ch_001


@pytest.mark.asyncio
async def test_compute_profile_no_watches(pool):
    """Should handle user with no watches gracefully."""
    await seed_user(pool)
    result = await compute_profile(TEST_USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_compute_profile_no_tags(pool):
    """Should handle videos without tags (untagged)."""
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001")
    # No tags seeded
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 3})

    result = await compute_profile(TEST_USER_ID)
    assert result is not None
    assert result["topic_count"] == 0  # No tags → no topics


@pytest.mark.asyncio
async def test_compute_profile_recompute_overwrites(pool):
    """Recomputing profile should overwrite old data."""
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001", "ch_001", subscriber_count=5000)
    await seed_video_tags(pool, "vid_001", topics=["topic_a"])
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 1})

    await compute_profile(TEST_USER_ID)

    # Now add more watches and recompute
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE user_video_watches SET watch_count = 10 WHERE user_id = $1 AND video_id = 'vid_001'",
            TEST_USER_ID,
        )

    await compute_profile(TEST_USER_ID)

    async with pool.acquire() as conn:
        profile = await conn.fetchrow(
            "SELECT topic_weights FROM user_profiles WHERE user_id = $1", TEST_USER_ID
        )
        topic_weights = json.loads(profile["topic_weights"])
        assert topic_weights["topic_a"] == 10  # Updated from 1 to 10
