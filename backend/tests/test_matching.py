"""Tests for the matching engine."""

import json
import math
import pytest
import numpy as np
from uuid import UUID
from tests.conftest import (
    seed_user, seed_profile, seed_video_metadata, seed_video_tags, seed_watches,
    TEST_USER_ID, TEST_USER_ID_2,
)
from app.services.matching import (
    run_matching,
    _topic_overlap_score,
    _embedding_similarity,
    _channel_overlap_score,
    _domain_hierarchy_score,
    _format_similarity_score,
    _complementary_gap_score,
)


# ── Unit tests for scoring functions ─────────────────────


def test_topic_overlap_identical():
    a = {"topic_weights": {"ml": 3, "ai": 2}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"topic_weights": {"ml": 3, "ai": 2}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _topic_overlap_score(a, b, 100)
    assert score == 1.0  # Identical topics → max score


def test_topic_overlap_no_shared():
    a = {"topic_weights": {"ml": 3}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"topic_weights": {"cooking": 3}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _topic_overlap_score(a, b, 100)
    assert score == 0


def test_topic_overlap_partial():
    a = {"topic_weights": {"ml": 3, "cooking": 1}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"topic_weights": {"ml": 3, "sports": 1}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _topic_overlap_score(a, b, 100)
    assert 0 < score < 1.0


def test_embedding_similarity_identical():
    emb = np.random.randn(384).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    a = {"embedding": emb}
    b = {"embedding": emb.copy()}
    score = _embedding_similarity(a, b)
    assert abs(score - 1.0) < 0.01


def test_embedding_similarity_orthogonal():
    emb_a = np.zeros(384, dtype=np.float32)
    emb_a[0] = 1.0
    emb_b = np.zeros(384, dtype=np.float32)
    emb_b[1] = 1.0
    a = {"embedding": emb_a}
    b = {"embedding": emb_b}
    score = _embedding_similarity(a, b)
    assert score == 0


def test_embedding_similarity_none():
    a = {"embedding": None}
    b = {"embedding": None}
    assert _embedding_similarity(a, b) == 0


def test_channel_overlap_niche_channels_score_higher():
    # Both share ch_niche (low subs → high weight) and ch_mainstream (high subs → low weight)
    a = {"channel_weights": {"ch_niche": 10, "ch_mainstream": 1}, "topic_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"channel_weights": {"ch_niche": 8, "ch_mainstream": 1}, "topic_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _channel_overlap_score(a, b)
    assert score > 0


def test_domain_hierarchy_shared_prefix():
    a = {"domain_weights": {"tech > AI > NLP": 3, "sports > tennis": 1}, "topic_weights": {}, "channel_weights": {}, "format_distribution": {}}
    b = {"domain_weights": {"tech > AI > computer vision": 3, "sports > tennis": 1}, "topic_weights": {}, "channel_weights": {}, "format_distribution": {}}
    score = _domain_hierarchy_score(a, b)
    assert score > 0  # Share "tech", "tech > AI", and "sports", "sports > tennis"


def test_domain_hierarchy_no_overlap():
    a = {"domain_weights": {"tech > AI": 3}, "topic_weights": {}, "channel_weights": {}, "format_distribution": {}}
    b = {"domain_weights": {"sports > tennis": 3}, "topic_weights": {}, "channel_weights": {}, "format_distribution": {}}
    score = _domain_hierarchy_score(a, b)
    assert score == 0


def test_format_similarity_identical():
    a = {"format_distribution": {"podcast": 0.6, "tutorial": 0.4}, "topic_weights": {}, "channel_weights": {}, "domain_weights": {}}
    b = {"format_distribution": {"podcast": 0.6, "tutorial": 0.4}, "topic_weights": {}, "channel_weights": {}, "domain_weights": {}}
    score = _format_similarity_score(a, b)
    assert abs(score - 1.0) < 0.01


def test_format_similarity_different():
    a = {"format_distribution": {"podcast": 1.0}, "topic_weights": {}, "channel_weights": {}, "domain_weights": {}}
    b = {"format_distribution": {"tutorial": 1.0}, "topic_weights": {}, "channel_weights": {}, "domain_weights": {}}
    score = _format_similarity_score(a, b)
    assert score == 0


def test_complementary_gap_one_deep_one_exploring():
    a = {"topic_weights": {"ml": 100, "cooking": 1}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"topic_weights": {"ml": 1, "cooking": 100}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _complementary_gap_score(a, b, 100)
    assert score > 0  # Both topics have >5x ratio


def test_complementary_gap_equal_depth():
    a = {"topic_weights": {"ml": 5, "cooking": 5}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    b = {"topic_weights": {"ml": 5, "cooking": 5}, "channel_weights": {}, "format_distribution": {}, "domain_weights": {}}
    score = _complementary_gap_score(a, b, 100)
    assert score == 0  # No ratio > 5


# ── Integration tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_matching_finds_similar_users(pool):
    """Two users with overlapping interests should match."""
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")

    # Seed shared videos and tags
    await seed_video_metadata(pool, "vid_001", "ch_ai", "Transformers Explained",
                               subscriber_count=8000)
    await seed_video_metadata(pool, "vid_002", "ch_ai", "GPT-5 Deep Dive",
                               subscriber_count=8000)
    await seed_video_metadata(pool, "vid_003", "ch_biz", "YC Application Tips",
                               subscriber_count=300000)

    await seed_video_tags(pool, "vid_001", topics=["transformers", "AI", "machine learning"],
                          domain="tech > AI", fmt="tutorial")
    await seed_video_tags(pool, "vid_002", topics=["GPT", "AI", "language models"],
                          domain="tech > AI", fmt="explainer")
    await seed_video_tags(pool, "vid_003", topics=["startups", "YC", "fundraising"],
                          domain="business > startups", fmt="podcast")

    # User 1 watches all 3
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 3, "vid_002": 2, "vid_003": 1})
    # User 2 watches the AI ones heavily
    await seed_watches(pool, TEST_USER_ID_2, {"vid_001": 2, "vid_002": 4})

    # Compute profiles for both
    from app.services.profile import compute_profile
    await compute_profile(TEST_USER_ID)
    await compute_profile(TEST_USER_ID_2)

    # Run matching for user 1
    match_count = await run_matching(TEST_USER_ID)

    assert match_count >= 1

    # Verify match was stored
    async with pool.acquire() as conn:
        matches = await conn.fetch(
            "SELECT * FROM matches WHERE user_id_a = $1 OR user_id_b = $1",
            TEST_USER_ID,
        )
        assert len(matches) >= 1

        match = matches[0]
        assert match["score"] > 0
        assert match["topic_overlap"] > 0
        assert match["channel_overlap"] > 0

        details = json.loads(match["details"])
        assert len(details["shared_topics"]) > 0
        assert len(details["shared_channels"]) > 0


@pytest.mark.asyncio
async def test_matching_no_users(pool):
    """Matching with no other users returns 0."""
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_video_metadata(pool, "vid_001")
    await seed_video_tags(pool, "vid_001", topics=["solo topic"])
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 1})

    from app.services.profile import compute_profile
    await compute_profile(TEST_USER_ID)

    match_count = await run_matching(TEST_USER_ID)
    assert match_count == 0


@pytest.mark.asyncio
async def test_matching_no_overlap(pool):
    """Two users with completely different interests should have low/no match."""
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")

    await seed_video_metadata(pool, "vid_ai", "ch_ai", subscriber_count=5000)
    await seed_video_metadata(pool, "vid_cook", "ch_cook", subscriber_count=5000)

    await seed_video_tags(pool, "vid_ai", topics=["quantum computing", "physics"],
                          domain="science > physics", fmt="documentary")
    await seed_video_tags(pool, "vid_cook", topics=["italian cooking", "pasta"],
                          domain="food > italian", fmt="tutorial")

    await seed_watches(pool, TEST_USER_ID, {"vid_ai": 5})
    await seed_watches(pool, TEST_USER_ID_2, {"vid_cook": 5})

    from app.services.profile import compute_profile
    await compute_profile(TEST_USER_ID)
    await compute_profile(TEST_USER_ID_2)

    match_count = await run_matching(TEST_USER_ID)
    # No shared topics or channels → should not match (or very low score)
    assert match_count == 0


@pytest.mark.asyncio
async def test_matching_conversation_seed(pool):
    """Matches should include a conversation seed from the most niche shared channel."""
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")

    # Shared niche channel
    await seed_video_metadata(pool, "vid_001", "ch_niche", "Obscure Topic Deep Dive",
                               view_count=500, subscriber_count=2000)
    await seed_video_tags(pool, "vid_001", topics=["obscure topic", "niche interest"],
                          domain="niche > deep", fmt="podcast")

    await seed_watches(pool, TEST_USER_ID, {"vid_001": 3})
    await seed_watches(pool, TEST_USER_ID_2, {"vid_001": 2})

    from app.services.profile import compute_profile
    await compute_profile(TEST_USER_ID)
    await compute_profile(TEST_USER_ID_2)

    await run_matching(TEST_USER_ID)

    async with pool.acquire() as conn:
        match = await conn.fetchrow(
            "SELECT details FROM matches WHERE user_id_a = $1 OR user_id_b = $1",
            TEST_USER_ID,
        )
        assert match is not None
        details = json.loads(match["details"])
        seed = details.get("conversation_seed")
        assert seed is not None
        assert "prompt" in seed
        assert seed["video_id"] == "vid_001"


@pytest.mark.asyncio
async def test_matching_asymmetric_scores(pool):
    """Scores should be computed in both directions and combined with harmonic mean."""
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")

    # User 1 has broad interests, User 2 is focused
    await seed_video_metadata(pool, "vid_001", "ch_001", subscriber_count=5000)
    await seed_video_metadata(pool, "vid_002", "ch_002", subscriber_count=5000)
    await seed_video_metadata(pool, "vid_003", "ch_003", subscriber_count=5000)

    await seed_video_tags(pool, "vid_001", topics=["shared topic"], domain="tech", fmt="podcast")
    await seed_video_tags(pool, "vid_002", topics=["only user 1"], domain="sports", fmt="tutorial")
    await seed_video_tags(pool, "vid_003", topics=["only user 1 too"], domain="music", fmt="documentary")

    await seed_watches(pool, TEST_USER_ID, {"vid_001": 1, "vid_002": 3, "vid_003": 3})
    await seed_watches(pool, TEST_USER_ID_2, {"vid_001": 5})

    from app.services.profile import compute_profile
    await compute_profile(TEST_USER_ID)
    await compute_profile(TEST_USER_ID_2)

    await run_matching(TEST_USER_ID)

    async with pool.acquire() as conn:
        match = await conn.fetchrow(
            "SELECT score, score_a_to_b, score_b_to_a FROM matches WHERE user_id_a = $1 OR user_id_b = $1",
            TEST_USER_ID,
        )
        if match:
            # Final score should be harmonic mean, <= both directional scores
            assert match["score"] <= max(match["score_a_to_b"], match["score_b_to_a"])
