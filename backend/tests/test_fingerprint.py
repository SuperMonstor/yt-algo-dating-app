"""Tests for GET /fingerprint and GET /fingerprint/{slug}."""

import pytest
from app.routes.fingerprint import classify_personality, generate_slug
from tests.conftest import (
    seed_user, seed_profile, seed_watches, seed_video_metadata,
    TEST_USER_ID,
)


# ── Unit tests for personality classification ────────────


def test_personality_podcast_brain():
    result = classify_personality(
        format_distribution={"podcast": 0.45, "interview": 0.15, "tutorial": 0.1},
        topic_weights={"ai": 3, "startups": 2, "fitness": 1},
        domain_weights={"tech > AI": 3, "business": 2},
    )
    assert result["label"] == "Podcast Brain"


def test_personality_deep_diver():
    # Few topics, high concentration
    topics = {f"topic_{i}": 10 - i for i in range(15)}
    result = classify_personality(
        format_distribution={"documentary": 0.5, "tutorial": 0.3},
        topic_weights=topics,
        domain_weights={"tech > AI": 8, "tech > ML": 5},
    )
    assert result["label"] == "Deep Diver"


def test_personality_polymath():
    # Many topics across many domains
    topics = {f"topic_{i}": 1.0 for i in range(100)}
    domains = {
        "tech > AI": 2, "tech > web": 1,
        "science > physics": 2, "science > biology": 1,
        "philosophy > ethics": 2,
        "sports > tennis": 1,
        "business > startups": 1,
    }
    result = classify_personality(
        format_distribution={"documentary": 0.3, "podcast": 0.3, "tutorial": 0.2},
        topic_weights=topics,
        domain_weights=domains,
    )
    assert result["label"] == "Polymath"


def test_personality_visual_learner():
    result = classify_personality(
        format_distribution={"tutorial": 0.35, "explainer": 0.15, "documentary": 0.2},
        topic_weights={f"topic_{i}": 1.0 for i in range(50)},
        domain_weights={"tech > programming": 3},
    )
    assert result["label"] == "Visual Learner"


def test_personality_culture_vulture():
    result = classify_personality(
        format_distribution={"documentary": 0.4, "review": 0.3},
        topic_weights={f"topic_{i}": 1.0 for i in range(50)},
        domain_weights={
            "music > jazz": 3, "music > classical": 2,
            "film > indie": 2, "art > modern": 1,
            "tech > AI": 0.5,
        },
    )
    assert result["label"] == "Culture Vulture"


def test_personality_niche_explorer_fallback():
    """Default personality when no strong signal."""
    result = classify_personality(
        format_distribution={"documentary": 0.3, "podcast": 0.2, "vlog": 0.2},
        topic_weights={f"topic_{i}": 1.0 for i in range(50)},
        domain_weights={"tech > AI": 2, "sports > tennis": 2},
    )
    assert result["label"] == "Niche Explorer"


# ── Slug generation ──────────────────────────────────────


def test_slug_is_deterministic():
    slug1 = generate_slug(TEST_USER_ID)
    slug2 = generate_slug(TEST_USER_ID)
    assert slug1 == slug2
    assert slug1.startswith("yt-")


def test_slug_differs_per_user():
    from tests.conftest import TEST_USER_ID_2
    assert generate_slug(TEST_USER_ID) != generate_slug(TEST_USER_ID_2)


# ── Integration tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_fingerprint_returns_full_data(client, pool):
    await seed_user(pool)

    # Seed videos + watches so niche queries work
    for i in range(5):
        await seed_video_metadata(
            pool, f"vid_{i:03d}", f"ch_{i:03d}",
            title=f"Video {i}", view_count=(i + 1) * 100,
            duration_seconds=600, subscriber_count=(i + 1) * 500,
        )
    await seed_watches(pool, TEST_USER_ID, {f"vid_{i:03d}": i + 1 for i in range(5)})
    await seed_profile(pool, TEST_USER_ID)

    resp = await client.get("/fingerprint")
    assert resp.status_code == 200
    data = resp.json()

    assert data["slug"].startswith("yt-")
    assert len(data["top_topics"]) > 0
    assert len(data["top_channels"]) > 0
    assert "podcast" in data["format_distribution"]
    assert data["watch_stats"]["total_videos"] > 0
    assert data["watch_stats"]["estimated_hours"] >= 0
    assert "label" in data["personality_type"]
    assert "description" in data["personality_type"]


@pytest.mark.asyncio
async def test_fingerprint_not_found(client):
    resp = await client.get("/fingerprint")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_fingerprint_accessible(client, pool):
    await seed_user(pool, status="active")
    await seed_video_metadata(pool, "vid_001")
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 3})
    await seed_profile(pool, TEST_USER_ID)

    slug = generate_slug(TEST_USER_ID)
    resp = await client.get(f"/fingerprint/{slug}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == slug


@pytest.mark.asyncio
async def test_public_fingerprint_not_found(client):
    resp = await client.get("/fingerprint/yt-nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_domain_distribution_normalized(client, pool):
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001")
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 1})
    await seed_profile(
        pool, TEST_USER_ID,
        domain_weights={"tech > AI": 6.0, "tech > web": 4.0, "sports > tennis": 2.0},
    )

    resp = await client.get("/fingerprint")
    data = resp.json()
    # Domain distribution should be top-level aggregated percentages
    dd = data["domain_distribution"]
    assert "tech" in dd
    # tech should be ~83.3% (10/12)
    assert dd["tech"] > 80
