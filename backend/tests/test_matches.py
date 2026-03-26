"""Tests for GET /matches."""

import pytest
from tests.conftest import (
    seed_user, seed_match,
    TEST_USER_ID, TEST_USER_ID_2,
)


@pytest.mark.asyncio
async def test_matches_returns_data(client, pool):
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")
    await seed_match(pool, TEST_USER_ID, TEST_USER_ID_2, score=0.82)

    resp = await client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 1
    match = data["matches"][0]
    assert match["match_user_id"] == str(TEST_USER_ID_2)
    assert match["score"] == 0.82
    assert "topic_overlap" in match["score_breakdown"]
    assert len(match["shared_topics"]) > 0
    assert match["conversation_seed"] is not None
    assert "prompt" in match["conversation_seed"]


@pytest.mark.asyncio
async def test_matches_empty_for_new_user(client, pool):
    await seed_user(pool, TEST_USER_ID, status="active")

    resp = await client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["matches"] == []


@pytest.mark.asyncio
async def test_matches_requires_active_status(client, pool):
    await seed_user(pool, TEST_USER_ID, status="processing")

    resp = await client.get("/matches")
    assert resp.status_code == 400
    assert "active" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_matches_not_found_without_user(client):
    resp = await client.get("/matches")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_matches_sorted_by_score(client, pool):
    user_3 = "33333333-3333-3333-3333-333333333333"
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_user(pool, TEST_USER_ID_2, status="active")

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, status) VALUES ($1::uuid, 'active')", user_3
        )

    await seed_match(pool, TEST_USER_ID, TEST_USER_ID_2, score=0.65)

    from uuid import UUID
    await seed_match(pool, TEST_USER_ID, UUID(user_3), score=0.91)

    resp = await client.get("/matches")
    data = resp.json()
    assert data["total"] == 2
    scores = [m["score"] for m in data["matches"]]
    assert scores == sorted(scores, reverse=True)
