"""
Background processing pipeline for takeout uploads.

Orchestrates: parse → fetch → embed → fingerprint → (matching when ready).
Runs as a FastAPI background task. Updates processing_jobs with progress.

LLM tagging is NOT part of this pipeline — it's done manually/offline.
Fingerprint is generated from embeddings + clusters + raw data.
"""

import json
import sys
from uuid import UUID
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from parse_watch_history import parse_watch_history_from_string, classify_shorts
from app.database import get_conn
from app.services.fetcher import fetch_missing_videos
from app.services.embedder import embed_missing_videos, compute_user_fingerprint
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
        3. embedding  — embed videos + assign to clusters (local, free)
        4. profiling  — compute fingerprint from embeddings + raw data
        5. done

    LLM tagging is done separately (manual/offline).
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

        # ── Stage 3: Embed videos + assign clusters ─────────
        await update_job(job_id, "embedding", {"stage": "embedding", "items_processed": 0, "items_total": len(video_ids)})

        async def on_embed_progress(done, total):
            await update_job(job_id, "embedding", {"stage": "embedding", "items_processed": done, "items_total": total})

        await embed_missing_videos(video_ids, on_progress=on_embed_progress)

        await update_job(job_id, "embedding", {
            "stage": "embedding",
            "items_processed": len(video_ids),
            "items_total": len(video_ids),
        })

        # ── Stage 4: Compute fingerprint ────────────────────
        await update_job(job_id, "profiling", {"stage": "profiling"})

        fingerprint = await compute_user_fingerprint(user_id)

        # Store fingerprint as JSON in user_profiles
        if fingerprint:
            async with get_conn() as conn:
                await conn.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id, topic_weights, channel_weights,
                        format_distribution, domain_weights,
                        total_long_form_videos, computed_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, now())
                    ON CONFLICT (user_id) DO UPDATE SET
                        topic_weights = $2, channel_weights = $3,
                        format_distribution = $4, domain_weights = $5,
                        total_long_form_videos = $6,
                        computed_at = now()
                    """,
                    user_id,
                    json.dumps(fingerprint.get("interest_dna", [])),
                    json.dumps({c["name"]: c["watch_count"] for c in fingerprint.get("obsessed_channels", [])}),
                    json.dumps(fingerprint.get("watch_personality", {})),
                    json.dumps(fingerprint.get("archetype", {})),
                    fingerprint.get("stats", {}).get("total_videos", 0),
                )

        await update_job(job_id, "profiling", {
            "stage": "profiling",
            "items_processed": 1,
            "items_total": 1,
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
