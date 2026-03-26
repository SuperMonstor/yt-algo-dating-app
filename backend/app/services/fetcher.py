"""
Async YouTube Data API v3 fetcher.

Fetches video and channel metadata, stores in Postgres cache.
Batches 50 IDs per API call (YouTube API limit).
"""

import re
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

import aiohttp

from app.config import get_settings
from app.database import get_conn

BATCH_SIZE = 50
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 date string to datetime, or None."""
    if not s:
        return None
    try:
        # Handle both "2024-01-15T10:30:00Z" and "2024-01-15T10:30:00.000Z"
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parse_duration(iso_duration: str) -> int:
    """Convert ISO 8601 duration (PT1H2M3S) to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


async def fetch_missing_videos(
    video_ids: List[str],
    on_progress=None,
) -> Dict[str, int]:
    """
    Fetch metadata for videos not already in the cache.

    Returns {"fetched": N, "not_found": M, "already_cached": K}.
    """
    settings = get_settings()
    api_key = settings.youtube_api_key
    if not api_key:
        return {"fetched": 0, "not_found": 0, "already_cached": len(video_ids), "skipped": True}

    # Find which IDs are missing from cache
    async with get_conn() as conn:
        cached = await conn.fetch(
            "SELECT video_id FROM video_metadata WHERE video_id = ANY($1)",
            video_ids,
        )
        not_found_rows = await conn.fetch(
            "SELECT video_id FROM videos_not_found WHERE video_id = ANY($1)",
            video_ids,
        )
        known_ids = {r["video_id"] for r in cached} | {r["video_id"] for r in not_found_rows}
        missing = [vid for vid in video_ids if vid not in known_ids]

    if not missing:
        return {"fetched": 0, "not_found": 0, "already_cached": len(video_ids)}

    fetched_total = 0
    not_found_ids = []
    batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]

    async with aiohttp.ClientSession() as session:
        for batch_idx, batch in enumerate(batches):
            results = await _fetch_video_batch(session, api_key, batch)

            # Store fetched metadata
            if results:
                async with get_conn() as conn:
                    for vid, data in results.items():
                        await conn.execute(
                            """
                            INSERT INTO video_metadata
                            (video_id, title, description, channel_id, channel_title,
                             category_id, tags, published_at, duration_seconds,
                             view_count, like_count, comment_count)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            ON CONFLICT (video_id) DO NOTHING
                            """,
                            vid, data["title"], data["description"],
                            data["channel_id"], data["channel_title"],
                            data["category_id"], json.dumps(data["tags"]),
                            data["published_at"], data["duration_seconds"],
                            data["view_count"], data["like_count"], data["comment_count"],
                        )
                fetched_total += len(results)

            # Track not found
            found = set(results.keys())
            batch_not_found = [vid for vid in batch if vid not in found]
            not_found_ids.extend(batch_not_found)

            if on_progress:
                await on_progress(len(known_ids) + fetched_total + len(not_found_ids), len(video_ids))

            # Gentle rate limiting
            if batch_idx < len(batches) - 1:
                await asyncio.sleep(0.1)

    # Mark not-found videos
    if not_found_ids:
        async with get_conn() as conn:
            await conn.executemany(
                "INSERT INTO videos_not_found (video_id) VALUES ($1) ON CONFLICT DO NOTHING",
                [(vid,) for vid in not_found_ids],
            )

    # Now fetch missing channel metadata for all fetched videos
    await _fetch_missing_channels(video_ids)

    return {
        "fetched": fetched_total,
        "not_found": len(not_found_ids),
        "already_cached": len(known_ids),
    }


async def _fetch_video_batch(
    session: aiohttp.ClientSession,
    api_key: str,
    video_ids: List[str],
) -> Dict[str, dict]:
    """Fetch metadata for up to 50 video IDs from YouTube API."""
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": ",".join(video_ids),
        "key": api_key,
    }

    try:
        async with session.get(
            "%s/videos" % YOUTUBE_API_BASE, params=params
        ) as resp:
            if resp.status == 403:
                return {}  # Quota exceeded
            resp.raise_for_status()
            data = await resp.json()
    except (aiohttp.ClientError, Exception):
        return {}

    results = {}
    for item in data.get("items", []):
        vid = item["id"]
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        stats = item.get("statistics", {})

        results[vid] = {
            "title": snippet.get("title"),
            "description": (snippet.get("description") or "")[:500],
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "category_id": snippet.get("categoryId"),
            "tags": snippet.get("tags", []),
            "published_at": _parse_iso_date(snippet.get("publishedAt")),
            "duration_seconds": _parse_duration(content.get("duration", "")),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }

    return results


async def _fetch_missing_channels(video_ids: List[str]):
    """Fetch channel metadata for any channels referenced by these videos but not yet cached."""
    settings = get_settings()
    api_key = settings.youtube_api_key
    if not api_key:
        return

    # Get channel IDs from video metadata that we just stored
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT vm.channel_id
            FROM video_metadata vm
            WHERE vm.video_id = ANY($1)
              AND vm.channel_id IS NOT NULL
              AND vm.channel_id NOT IN (SELECT channel_id FROM channel_metadata)
              AND vm.channel_id NOT IN (SELECT channel_id FROM channels_not_found)
            """,
            video_ids,
        )
        missing_channels = [r["channel_id"] for r in rows]

    if not missing_channels:
        return

    batches = [missing_channels[i:i + BATCH_SIZE] for i in range(0, len(missing_channels), BATCH_SIZE)]
    not_found_channels = []

    async with aiohttp.ClientSession() as session:
        for batch_idx, batch in enumerate(batches):
            results = await _fetch_channel_batch(session, api_key, batch)

            if results:
                async with get_conn() as conn:
                    for cid, data in results.items():
                        await conn.execute(
                            """
                            INSERT INTO channel_metadata
                            (channel_id, title, description, custom_url, country,
                             published_at, subscriber_count, video_count, view_count,
                             hidden_subscriber_count, keywords)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (channel_id) DO NOTHING
                            """,
                            cid, data["title"], data["description"],
                            data["custom_url"], data["country"],
                            data["published_at"], data["subscriber_count"],
                            data["video_count"], data["view_count"],
                            data["hidden_subscriber_count"], data["keywords"],
                        )

            found = set(results.keys())
            not_found_channels.extend([cid for cid in batch if cid not in found])

            if batch_idx < len(batches) - 1:
                await asyncio.sleep(0.1)

    if not_found_channels:
        async with get_conn() as conn:
            await conn.executemany(
                "INSERT INTO channels_not_found (channel_id) VALUES ($1) ON CONFLICT DO NOTHING",
                [(cid,) for cid in not_found_channels],
            )


async def _fetch_channel_batch(
    session: aiohttp.ClientSession,
    api_key: str,
    channel_ids: List[str],
) -> Dict[str, dict]:
    """Fetch metadata for up to 50 channel IDs from YouTube API."""
    params = {
        "part": "snippet,statistics,brandingSettings",
        "id": ",".join(channel_ids),
        "key": api_key,
    }

    try:
        async with session.get(
            "%s/channels" % YOUTUBE_API_BASE, params=params
        ) as resp:
            if resp.status == 403:
                return {}
            resp.raise_for_status()
            data = await resp.json()
    except (aiohttp.ClientError, Exception):
        return {}

    results = {}
    for item in data.get("items", []):
        cid = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        branding = item.get("brandingSettings", {}).get("channel", {})

        results[cid] = {
            "title": snippet.get("title"),
            "description": (snippet.get("description") or "")[:500],
            "custom_url": snippet.get("customUrl"),
            "country": snippet.get("country"),
            "published_at": _parse_iso_date(snippet.get("publishedAt")),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
            "keywords": branding.get("keywords", ""),
        }

    return results
