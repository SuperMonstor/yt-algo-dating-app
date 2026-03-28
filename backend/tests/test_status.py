"""Tests for GET /status/{job_id}."""

import json
from uuid import uuid4

import pytest
from tests.conftest import seed_user, TEST_USER_ID


@pytest.mark.asyncio
async def test_status_returns_job(client, pool):
    await seed_user(pool)
    job_id = uuid4()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO processing_jobs (job_id, user_id, status, progress)
            VALUES ($1, $2, 'fetching', $3)
            """,
            job_id, TEST_USER_ID,
            json.dumps({"stage": "fetching", "items_processed": 50, "items_total": 200}),
        )

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fetching"
    assert data["progress"]["stage"] == "fetching"
    assert data["progress"]["items_processed"] == 50
    assert data["progress"]["items_total"] == 200


@pytest.mark.asyncio
async def test_status_not_found(client):
    resp = await client.get(f"/status/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_wrong_user(client, pool):
    """User A cannot see User B's job."""
    from tests.conftest import TEST_USER_ID_2
    await seed_user(pool, TEST_USER_ID_2)
    job_id = uuid4()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO processing_jobs (job_id, user_id, status)
            VALUES ($1, $2, 'queued')
            """,
            job_id, TEST_USER_ID_2,
        )

    # client is authenticated as TEST_USER_ID, not TEST_USER_ID_2
    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_done_with_no_error(client, pool):
    await seed_user(pool)
    job_id = uuid4()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO processing_jobs (job_id, user_id, status, progress)
            VALUES ($1, $2, 'done', $3)
            """,
            job_id, TEST_USER_ID,
            json.dumps({"stage": "done"}),
        )

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["error"] is None


@pytest.mark.asyncio
async def test_status_failed_with_error(client, pool):
    await seed_user(pool)
    job_id = uuid4()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO processing_jobs (job_id, user_id, status, error)
            VALUES ($1, $2, 'failed', 'YouTube API quota exceeded')
            """,
            job_id, TEST_USER_ID,
        )

    resp = await client.get(f"/status/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "quota" in data["error"].lower()
