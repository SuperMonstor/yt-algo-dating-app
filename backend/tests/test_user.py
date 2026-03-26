"""Tests for DELETE /user."""

import pytest
from tests.conftest import (
    seed_user, seed_profile, seed_watches, seed_match,
    seed_video_metadata,
    TEST_USER_ID, TEST_USER_ID_2,
)


@pytest.mark.asyncio
async def test_delete_user(client, pool):
    await seed_user(pool)

    resp = await client.delete("/user")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify user is gone
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", TEST_USER_ID)
        assert user is None


@pytest.mark.asyncio
async def test_delete_cascades_all_data(client, pool):
    """Deleting a user should cascade to watches, profile, indices, matches, jobs."""
    await seed_user(pool)
    await seed_user(pool, TEST_USER_ID_2)
    await seed_video_metadata(pool, "vid_001")
    await seed_watches(pool, TEST_USER_ID, {"vid_001": 3})
    await seed_profile(pool, TEST_USER_ID)
    await seed_match(pool, TEST_USER_ID, TEST_USER_ID_2, score=0.7)

    # Add index entries
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO topic_user_index (topic, user_id, weight) VALUES ('ai', $1, 3.5)",
            TEST_USER_ID,
        )
        await conn.execute(
            "INSERT INTO channel_user_index (channel_id, user_id, weight) VALUES ('ch_001', $1, 2.0)",
            TEST_USER_ID,
        )
        await conn.execute(
            "INSERT INTO processing_jobs (user_id, status) VALUES ($1, 'done')",
            TEST_USER_ID,
        )

    resp = await client.delete("/user")
    assert resp.status_code == 200

    # Verify all related data is gone
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT COUNT(*) FROM user_video_watches WHERE user_id = $1", TEST_USER_ID) == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM user_profiles WHERE user_id = $1", TEST_USER_ID) == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM topic_user_index WHERE user_id = $1", TEST_USER_ID) == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM channel_user_index WHERE user_id = $1", TEST_USER_ID) == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM processing_jobs WHERE user_id = $1", TEST_USER_ID) == 0

        # Matches involving this user should also be gone
        match_count = await conn.fetchval(
            "SELECT COUNT(*) FROM matches WHERE user_id_a = $1 OR user_id_b = $1",
            TEST_USER_ID,
        )
        assert match_count == 0

    # But video_metadata (cache) should still exist — it's shared public data
    async with pool.acquire() as conn:
        vid = await conn.fetchval("SELECT video_id FROM video_metadata WHERE video_id = 'vid_001'")
        assert vid == "vid_001"


@pytest.mark.asyncio
async def test_delete_nonexistent_user(client):
    resp = await client.delete("/user")
    assert resp.status_code == 404
