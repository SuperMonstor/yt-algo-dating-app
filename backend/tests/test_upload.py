"""Tests for POST /upload and POST /reupload."""

import pytest
from tests.conftest import seed_user, TEST_USER_ID


MINIMAL_WATCH_HTML = """
<html><body>
<div class="outer-cell">
Watched <a href="https://www.youtube.com/watch?v=abc123">Test Video Title</a><br>
<a href="https://www.youtube.com/channel/UCtest123">Test Channel</a><br>
Jan 15, 2025, 10:30:00 AM GMT+05:30
</div></div></div>
<div class="outer-cell">
Watched <a href="https://www.youtube.com/watch?v=def456">Another Video</a><br>
<a href="https://www.youtube.com/channel/UCtest456">Another Channel</a><br>
Jan 15, 2025, 9:00:00 AM GMT+05:30
</div></div></div>
</body></html>
"""


@pytest.mark.asyncio
async def test_upload_creates_user_and_job(client, pool):
    resp = await client.post(
        "/upload",
        files={"file": ("watch-history.html", MINIMAL_WATCH_HTML.encode(), "text/html")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    assert "job_id" in data

    # Verify user was created in DB
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", TEST_USER_ID)
        assert user is not None
        # Background task may complete before we check, so status could be processing or active
        assert user["status"] in ("processing", "active")

        # Verify job was created
        job = await conn.fetchrow("SELECT * FROM processing_jobs WHERE job_id = $1::uuid", data["job_id"])
        assert job is not None


@pytest.mark.asyncio
async def test_upload_rejects_non_html(client):
    resp = await client.post(
        "/upload",
        files={"file": ("data.json", b'{"key": "value"}', "application/json")},
    )
    assert resp.status_code == 400
    assert "html" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(client):
    resp = await client.post(
        "/upload",
        files={"file": ("watch-history.html", b"", "text/html")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reupload_requires_existing_user(client):
    resp = await client.post(
        "/reupload",
        files={"file": ("watch-history.html", MINIMAL_WATCH_HTML.encode(), "text/html")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reupload_works_for_existing_user(client, pool):
    await seed_user(pool, TEST_USER_ID, status="active")

    resp = await client.post(
        "/reupload",
        files={"file": ("watch-history.html", MINIMAL_WATCH_HTML.encode(), "text/html")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
