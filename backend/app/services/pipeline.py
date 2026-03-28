"""
Background processing pipeline for takeout uploads.

Orchestrates: parse → fetch → tag → profile → (matching when ready).
Runs as a FastAPI background task. Updates processing_jobs with progress.
"""

import json
import sys
import os
from uuid import UUID
from pathlib import Path

# Add parent backend dir to path so we can import existing pipeline modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from parse_watch_history import parse_watch_history_from_string, classify_shorts
from app.database import get_conn
from app.services.fetcher import fetch_missing_videos
from app.services.tagger import tag_missing_videos
from app.services.profile import compute_profile
from app.services.matching import run_matching


async def update_job(job_id: UUID, status: str, progress: dict = None, error: str = None):
    """Update a processing job's status and progress."""
    async with get_conn() as conn:
        await conn.execute(
            """
            UPDATE processing_jobs
            SET status = $2, progress = $3, error = $4, updated_at = now()
            WHERE job_id = $1
            """,
            job_id,
            status,
            json.dumps(progress or {}),
            error,
        )


async def run_pipeline(user_id: UUID, job_id: UUID, html_content: str, is_reupload: bool = False):
    """
    Run the full processing pipeline as a background task.

    Stages:
        1. parsing    — extract video IDs from HTML
        2. fetching   — fetch missing video/channel metadata from YouTube API
        3. tagging    — LLM-tag untagged videos
        4. profiling  — compute topic_weights, embedding, etc.
        5. matching   — run matching (placeholder for now)
        6. done
    """
    try:
        # ── Stage 1: Parse ──────────────────────────────────
        await update_job(job_id, "parsing", {"stage": "parsing"})

        entries = parse_watch_history_from_string(html_content)
        entries = classify_shorts(entries)
        long_entries = [e for e in entries if e["content_type"] == "long"]

        # Build {video_id: watch_count}
        video_watches: dict[str, int] = {}
        for entry in long_entries:
            vid = entry["video_id"]
            video_watches[vid] = video_watches.get(vid, 0) + 1

        await update_job(job_id, "parsing", {
            "stage": "parsing",
            "items_processed": len(video_watches),
            "items_total": len(video_watches),
        })

        # ── Store watches ───────────────────────────────────
        async with get_conn() as conn:
            if is_reupload:
                # Additive merge: update existing counts, add new entries
                for vid, count in video_watches.items():
                    await conn.execute(
                        """
                        INSERT INTO user_video_watches (user_id, video_id, watch_count)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, video_id)
                        DO UPDATE SET watch_count = user_video_watches.watch_count + $3
                        """,
                        user_id, vid, count,
                    )
            else:
                # First upload: clear any stale data, insert fresh
                await conn.execute(
                    "DELETE FROM user_video_watches WHERE user_id = $1", user_id
                )
                await conn.executemany(
                    """
                    INSERT INTO user_video_watches (user_id, video_id, watch_count)
                    VALUES ($1, $2, $3)
                    """,
                    [(user_id, vid, count) for vid, count in video_watches.items()],
                )

        # ── Stage 2: Fetch missing metadata ─────────────────
        video_ids = list(video_watches.keys())
        await update_job(job_id, "fetching", {"stage": "fetching", "items_processed": 0, "items_total": len(video_ids)})

        async def on_fetch_progress(done, total):
            await update_job(job_id, "fetching", {"stage": "fetching", "items_processed": done, "items_total": total})

        await fetch_missing_videos(video_ids, on_progress=on_fetch_progress)

        await update_job(job_id, "fetching", {
            "stage": "fetching",
            "items_processed": len(video_ids),
            "items_total": len(video_ids),
        })

        # ── Stage 3: Tag untagged videos ────────────────────
        await update_job(job_id, "tagging", {"stage": "tagging", "items_processed": 0, "items_total": len(video_ids)})

        async def on_tag_progress(done, total):
            await update_job(job_id, "tagging", {"stage": "tagging", "items_processed": done, "items_total": total})

        await tag_missing_videos(video_ids, on_progress=on_tag_progress)

        await update_job(job_id, "tagging", {
            "stage": "tagging",
            "items_processed": len(video_ids),
            "items_total": len(video_ids),
        })

        # ── Stage 4: Compute profile ───────────────────────
        await update_job(job_id, "profiling", {"stage": "profiling"})

        profile_stats = await compute_profile(user_id)

        await update_job(job_id, "profiling", {
            "stage": "profiling",
            "items_processed": 1,
            "items_total": 1,
        })

        # ── Stage 5: Matching ──────────────────────────────
        await update_job(job_id, "matching", {"stage": "matching"})

        match_count = await run_matching(user_id)

        await update_job(job_id, "matching", {
            "stage": "matching",
            "items_processed": match_count,
            "items_total": match_count,
        })

        # ── Done ───────────────────────────────────────────
        async with get_conn() as conn:
            await conn.execute(
                "UPDATE users SET status = 'active', updated_at = now() WHERE user_id = $1",
                user_id,
            )
        await update_job(job_id, "done", {"stage": "done"})

    except Exception as e:
        await update_job(job_id, "failed", error=str(e))
        async with get_conn() as conn:
            await conn.execute(
                "UPDATE users SET status = 'active', updated_at = now() WHERE user_id = $1",
                user_id,
            )
