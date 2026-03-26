"""Tests for GET /health and GET /stats."""

import pytest
from tests.conftest import seed_user, seed_video_metadata, TEST_USER_ID


@pytest.mark.asyncio
async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_stats_empty(client):
    resp = await client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["users"] == 0
    assert data["active_users"] == 0
    assert data["videos_cached"] == 0
    assert data["channels_cached"] == 0
    assert data["videos_tagged"] == 0
    assert data["active_jobs"] == 0


@pytest.mark.asyncio
async def test_stats_with_data(client, pool):
    await seed_user(pool, TEST_USER_ID, status="active")
    await seed_video_metadata(pool, "vid_001")

    resp = await client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["users"] == 1
    assert data["active_users"] == 1
    assert data["videos_cached"] == 1
    assert data["channels_cached"] == 1
