"""
Shared test fixtures.

- Connects to real Postgres test container (docker-compose.test.yml)
- Applies schema.sql, cleans tables between tests
- Provides an authenticated test client (bypasses JWT)
"""

import json
import asyncio
from pathlib import Path
from uuid import UUID, uuid4
from typing import Optional

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Override settings BEFORE importing app modules
import os
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5433/ytalgo_test"
os.environ["SUPABASE_URL"] = "http://localhost"
os.environ["SUPABASE_JWT_SECRET"] = "test-secret-key-at-least-32-chars-long!!"

from app.main import app
from app.auth import get_current_user
from app import database as db_module

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"
DB_URL = "postgresql://test:test@localhost:5433/ytalgo_test"

# Fixed test user IDs
TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_USER_ID_2 = UUID("22222222-2222-2222-2222-222222222222")

_schema_applied = False


@pytest_asyncio.fixture
async def pool():
    """Create a connection pool for this test."""
    global _schema_applied
    p = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    if not _schema_applied:
        schema_sql = SCHEMA_PATH.read_text()
        async with p.acquire() as conn:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            await conn.execute(schema_sql)
        _schema_applied = True

    # Inject pool into the app's database module
    db_module.pool = p

    yield p

    # Clean tables after test
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM matches")
        await conn.execute("DELETE FROM processing_jobs")
        await conn.execute("DELETE FROM topic_user_index")
        await conn.execute("DELETE FROM channel_user_index")
        await conn.execute("DELETE FROM user_profiles")
        await conn.execute("DELETE FROM user_video_watches")
        await conn.execute("DELETE FROM users")
        await conn.execute("DELETE FROM video_tags")
        await conn.execute("DELETE FROM video_metadata")
        await conn.execute("DELETE FROM channel_metadata")
        await conn.execute("DELETE FROM videos_not_found")
        await conn.execute("DELETE FROM channels_not_found")
        await conn.execute("DELETE FROM global_stats")

    await p.close()


@pytest_asyncio.fixture
async def client(pool):
    """Test client authenticated as TEST_USER_ID."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_user2(pool):
    """Test client authenticated as TEST_USER_ID_2."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID_2
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Seed helpers ─────────────────────────────────────────────


async def seed_user(pool, user_id=TEST_USER_ID, status="active"):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, display_name, status)
            VALUES ($1, 'Test User', $2)
            ON CONFLICT (user_id) DO UPDATE SET status = $2
            """,
            user_id, status,
        )


async def seed_video_metadata(pool, video_id, channel_id="ch_001", title="Test Video",
                               view_count=1000, duration_seconds=600, subscriber_count=5000):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO channel_metadata (channel_id, title, subscriber_count)
            VALUES ($1, $2, $3)
            ON CONFLICT (channel_id) DO NOTHING
            """,
            channel_id, "Channel %s" % channel_id, subscriber_count,
        )
        await conn.execute(
            """
            INSERT INTO video_metadata (video_id, title, channel_id, channel_title,
                                        view_count, duration_seconds, category_id)
            VALUES ($1, $2, $3, $4, $5, $6, '22')
            ON CONFLICT (video_id) DO NOTHING
            """,
            video_id, title, channel_id, "Channel %s" % channel_id,
            view_count, duration_seconds,
        )


async def seed_video_tags(pool, video_id, topics=None, domain="tech > AI", fmt="podcast"):
    if topics is None:
        topics = ["machine learning", "neural networks"]
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO video_tags (video_id, topics, domain, format, model)
            VALUES ($1, $2, $3, $4, 'test')
            ON CONFLICT (video_id) DO NOTHING
            """,
            video_id, json.dumps(topics), domain, fmt,
        )


async def seed_watches(pool, user_id, watches):
    """watches = {video_id: count}"""
    async with pool.acquire() as conn:
        for vid, count in watches.items():
            await conn.execute(
                """
                INSERT INTO user_video_watches (user_id, video_id, watch_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, video_id) DO NOTHING
                """,
                user_id, vid, count,
            )


async def seed_profile(pool, user_id=TEST_USER_ID, topic_weights=None, channel_weights=None,
                        format_distribution=None, domain_weights=None,
                        total_long_form_videos=100):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_profiles (user_id, topic_weights, channel_weights,
                                       format_distribution, domain_weights,
                                       total_long_form_videos, computed_at)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            ON CONFLICT (user_id) DO UPDATE SET
                topic_weights = $2, channel_weights = $3,
                format_distribution = $4, domain_weights = $5,
                total_long_form_videos = $6, computed_at = now()
            """,
            user_id,
            json.dumps(topic_weights or {"machine learning": 3.5, "startups": 2.1, "philosophy": 1.8}),
            json.dumps(channel_weights or {"ch_001": 4.2, "ch_002": 3.1, "ch_003": 1.5}),
            json.dumps(format_distribution or {"podcast": 0.6, "tutorial": 0.25, "documentary": 0.15}),
            json.dumps(domain_weights or {"tech > AI": 3.0, "business > startups": 2.0, "philosophy > stoicism": 1.5}),
            total_long_form_videos,
        )


async def seed_match(pool, user_a, user_b, score=0.82):
    if str(user_a) > str(user_b):
        user_a, user_b = user_b, user_a
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO matches (user_id_a, user_id_b, score, score_a_to_b, score_b_to_a,
                                 topic_overlap, embedding_sim, channel_overlap,
                                 domain_sim, format_sim, complementary, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            user_a, user_b, score, 0.85, 0.79,
            0.35, 0.25, 0.20, 0.10, 0.05, 0.05,
            json.dumps({
                "shared_topics": [{"topic": "machine learning", "idf": 2.5}],
                "shared_channels": [{"channel_id": "ch_001", "title": "AI Channel", "subs": 5000}],
                "complementary_topics": [{"topic": "rust programming", "you": "deep", "them": "exploring"}],
                "conversation_seed": {
                    "video_id": "vid_001",
                    "title": "The Future of AI",
                    "channel": "AI Channel",
                    "prompt": "You both watch AI Channel. What did you think of their latest?",
                },
            }),
        )
