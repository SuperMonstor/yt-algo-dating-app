"""Tests for GET /profile."""

import pytest
from tests.conftest import (
    seed_user, seed_profile, seed_video_metadata,
    TEST_USER_ID,
)


@pytest.mark.asyncio
async def test_profile_returns_data(client, pool):
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001", "ch_001", subscriber_count=5000)
    await seed_video_metadata(pool, "vid_002", "ch_002", subscriber_count=50000)
    await seed_video_metadata(pool, "vid_003", "ch_003", subscriber_count=200)
    await seed_profile(pool, TEST_USER_ID)

    resp = await client.get("/profile")
    assert resp.status_code == 200
    data = resp.json()

    assert data["user_id"] == str(TEST_USER_ID)
    assert data["total_long_form_videos"] == 100
    assert len(data["top_topics"]) > 0
    assert len(data["top_channels"]) > 0
    assert data["format_distribution"]["podcast"] == 0.6

    # Topics should be sorted by weight descending
    weights = [t["weight"] for t in data["top_topics"]]
    assert weights == sorted(weights, reverse=True)


@pytest.mark.asyncio
async def test_profile_not_found_without_upload(client):
    resp = await client.get("/profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_channels_enriched_with_metadata(client, pool):
    await seed_user(pool)
    await seed_video_metadata(pool, "vid_001", "ch_001", subscriber_count=12345)
    await seed_profile(pool, TEST_USER_ID, channel_weights={"ch_001": 5.0})

    resp = await client.get("/profile")
    assert resp.status_code == 200
    data = resp.json()

    ch = data["top_channels"][0]
    assert ch["channel_id"] == "ch_001"
    assert ch["subscriber_count"] == 12345
    assert ch["title"] is not None
