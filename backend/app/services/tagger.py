"""
Async LLM video tagger.

Tags untagged videos using Anthropic API (Claude Haiku).
Each video gets: topics (3-5), domain (hierarchical), format, guest.
Batches 20 videos per LLM call for efficiency.
"""

import json
import asyncio
from typing import Dict, List

import anthropic

from app.config import get_settings
from app.database import get_conn

BATCH_SIZE = 20

SYSTEM_PROMPT = """You are a video content tagger. Given a batch of YouTube videos (title, channel, tags, description), classify each one.

For each video, return:
- topics: 3-5 specific topic tags (lowercase, e.g. "sleep science", "startup funding", "tennis highlights")
- domain: hierarchical category (e.g. "self-improvement > health > sleep", "sports > tennis", "tech > AI")
- format: one of: podcast, interview, tutorial, music video, documentary, vlog, comedy sketch, highlights, clip, reaction, review, explainer, news, live performance, compilation, other
- guest: name of the guest if it's an interview/podcast and you can identify them from the title/description, otherwise null

Return ONLY a JSON array with one object per video, in the same order as input. Each object must have keys: video_id, topics, domain, format, guest.

Be specific with topics — "artificial intelligence" is better than "technology". "marathon training" is better than "fitness"."""


def _build_batch_prompt(videos: List[dict]) -> str:
    """Build the user prompt for a batch of videos."""
    lines = []
    for i, v in enumerate(videos):
        tags_str = ", ".join(v.get("tags", [])[:8]) if v.get("tags") else ""
        desc = (v.get("description") or "")[:200].replace("\n", " ")
        lines.append(
            "[%d] video_id: %s\n"
            "    title: %s\n"
            "    channel: %s\n"
            "    tags: %s\n"
            "    description: %s" % (
                i + 1, v["video_id"],
                v.get("title", ""),
                v.get("channel_title", ""),
                tags_str,
                desc,
            )
        )
    return "\n\n".join(lines)


def _parse_llm_response(raw: str, video_ids: List[str]) -> Dict[str, dict]:
    """Parse the LLM JSON response into {video_id: tag_data}."""
    try:
        data = json.loads(raw)

        if isinstance(data, dict):
            items = data.get("results", data.get("videos", []))
            if not items:
                if any(vid in data for vid in video_ids):
                    results = {}
                    for vid in video_ids:
                        if vid in data:
                            entry = data[vid]
                            results[vid] = {
                                "topics": entry.get("topics", []),
                                "domain": entry.get("domain", ""),
                                "format": entry.get("format", ""),
                                "guest": entry.get("guest"),
                            }
                    return results
                for v in data.values():
                    if isinstance(v, list):
                        items = v
                        break
        elif isinstance(data, list):
            items = data
        else:
            return {}

        results = {}
        for i, item in enumerate(items):
            vid = item.get("video_id") or (video_ids[i] if i < len(video_ids) else None)
            if vid:
                results[vid] = {
                    "topics": item.get("topics", []),
                    "domain": item.get("domain", ""),
                    "format": item.get("format", ""),
                    "guest": item.get("guest"),
                }
        return results
    except (json.JSONDecodeError, KeyError, IndexError):
        return {}


async def tag_missing_videos(
    video_ids: List[str],
    on_progress=None,
) -> Dict[str, int]:
    """
    Tag videos that don't have LLM tags yet.

    Returns {"tagged": N, "already_tagged": M, "failed": K}.
    """
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        return {"tagged": 0, "already_tagged": len(video_ids), "failed": 0, "skipped": True}

    # Find untagged videos that have metadata
    async with get_conn() as conn:
        tagged_rows = await conn.fetch(
            "SELECT video_id FROM video_tags WHERE video_id = ANY($1)",
            video_ids,
        )
        tagged_ids = {r["video_id"] for r in tagged_rows}
        untagged = [vid for vid in video_ids if vid not in tagged_ids]

        if not untagged:
            return {"tagged": 0, "already_tagged": len(video_ids), "failed": 0}

        # Load metadata for untagged videos
        meta_rows = await conn.fetch(
            """
            SELECT video_id, title, description, channel_title, tags
            FROM video_metadata
            WHERE video_id = ANY($1)
            """,
            untagged,
        )
        meta_map = {}
        for row in meta_rows:
            tags_raw = row["tags"]
            if isinstance(tags_raw, str):
                try:
                    tags = json.loads(tags_raw)
                except json.JSONDecodeError:
                    tags = []
            else:
                tags = tags_raw or []

            meta_map[row["video_id"]] = {
                "video_id": row["video_id"],
                "title": row["title"],
                "description": row["description"],
                "channel_title": row["channel_title"],
                "tags": tags,
            }

    # Only tag videos that have metadata
    taggable = [meta_map[vid] for vid in untagged if vid in meta_map]

    if not taggable:
        return {"tagged": 0, "already_tagged": len(tagged_ids), "failed": len(untagged)}

    # Batch and tag
    batches = [taggable[i:i + BATCH_SIZE] for i in range(0, len(taggable), BATCH_SIZE)]
    client = anthropic.Anthropic(api_key=api_key)
    model = "claude-haiku-4-5-20251001"

    total_tagged = 0
    total_failed = 0

    for batch_idx, batch in enumerate(batches):
        batch_video_ids = [v["video_id"] for v in batch]
        prompt = _build_batch_prompt(batch)

        try:
            response = await asyncio.to_thread(
                _call_anthropic, client, model, prompt
            )

            if response:
                results = _parse_llm_response(response, batch_video_ids)
                if results:
                    async with get_conn() as conn:
                        for vid, tag_data in results.items():
                            await conn.execute(
                                """
                                INSERT INTO video_tags (video_id, topics, domain, format, guest, raw_response, model)
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                ON CONFLICT (video_id) DO NOTHING
                                """,
                                vid,
                                json.dumps(tag_data["topics"]),
                                tag_data["domain"],
                                tag_data["format"],
                                tag_data.get("guest"),
                                response,
                                model,
                            )
                    total_tagged += len(results)
                    total_failed += len(batch) - len(results)
                else:
                    total_failed += len(batch)
            else:
                total_failed += len(batch)
        except Exception:
            total_failed += len(batch)

        if on_progress:
            await on_progress(len(tagged_ids) + total_tagged + total_failed, len(video_ids))

        # Rate limiting between batches
        if batch_idx < len(batches) - 1:
            await asyncio.sleep(0.5)

    return {
        "tagged": total_tagged,
        "already_tagged": len(tagged_ids),
        "failed": total_failed,
    }


def _call_anthropic(client: anthropic.Anthropic, model: str, user_prompt: str) -> str:
    """Sync call to Anthropic API (run in thread to avoid blocking event loop)."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
        )
        return response.content[0].text
    except Exception:
        return None
