"""
Video tagger (V3).

Tags every video via LLM (Haiku) through the Claude Max proxy.
Enriched context: title + channel + creator tags + cleaned description
+ YouTube categoryId + video duration + channel description.

LLM backend: Claude Max proxy (localhost:3456, OpenAI-compatible)
or Anthropic API (direct, pay-per-token fallback).

Batches 15 videos per LLM call for optimal quality.
"""

import re
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional

from app.config import get_settings
from app.database import get_conn

LLM_BATCH_SIZE = 15
PROXY_URL = "http://localhost:3456/v1/chat/completions"
PROXY_MODEL = "claude-haiku-4"

# ── YouTube category names ────────────────────────────────────
CATEGORY_NAMES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "29": "Nonprofits & Activism",
}

# ── V3 system prompt (optimized for Haiku specificity) ────────
SYSTEM_PROMPT = """You are a video content tagger for a dating app. Your tags match people with eerily similar interests — specificity is EVERYTHING.

For each video, return:
- topics: 3-5 tags. MAXIMALLY specific. Use proper nouns, show/person/brand names, specific concepts.
  GOOD: "bb ki vines angry masterji", "jannik sinner australian open 2026", "fogg vs axe india brand war"
  BAD: "comedy", "tennis", "brand competition"
- domain: hierarchical, 3+ levels. "sports > tennis > australian open highlights" NOT "sports > tennis"
- format: one of: podcast, interview, tutorial, music video, documentary, vlog, comedy sketch, highlights, clip, reaction, review, explainer, news, live performance, compilation, ad, other
- guest: guest name if identifiable, null otherwise

Return ONLY a JSON array. Keys: video_id, topics, domain, format, guest.

RULES:
- NEVER use generic words as topics: comedy, entertainment, music, content, viral, trending, video, funny, interesting
- ALWAYS name the specific person, show, brand, game, or concept
- Use the channel name and category as context clues
- Duration helps detect format: <2min = clip/ad, 2-15min = most formats, 15-60min = documentary/tutorial, >60min = podcast/lecture
- If it's clearly an advertisement, set format to "ad"
- Think: would TWO people sharing this exact tag be a meaningful signal?"""


# ── Description cleaner ───────────────────────────────────────

_LINK_RE = re.compile(r'https?://\S+')
_SOCIAL_RE = re.compile(r'(instagram|twitter|tiktok|facebook|discord|twitch|patreon|linkedin)\.com|@\w{3,}', re.I)
_SUB_RE = re.compile(r'(subscribe|notification|bell icon|like and)', re.I)
_SPONSOR_RE = re.compile(r'(sponsor|promo code|use code|discount|affiliate)', re.I)
_FOLLOW_RE = re.compile(r'^(follow|connect|find me|my social|business inquir)', re.I)


def _clean_description(desc: str, max_chars: int = 150) -> str:
    """Strip boilerplate from YouTube description, return useful text."""
    if not desc:
        return ""
    lines = desc.split("\n")
    clean = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _LINK_RE.search(line):
            continue
        if _SOCIAL_RE.search(line):
            continue
        if _SUB_RE.search(line):
            continue
        if _SPONSOR_RE.search(line):
            continue
        if line.startswith("#") and len(line) < 100:
            continue
        if line.startswith("---") or line.startswith("===") or line.startswith("__"):
            continue
        if len(line) < 5:
            continue
        if _FOLLOW_RE.search(line):
            break
        clean.append(line)
    return " ".join(clean)[:max_chars]


def _clean_channel_desc(desc: str, max_chars: int = 100) -> str:
    """Extract the first useful line from a channel description."""
    if not desc:
        return ""
    for line in desc.split("\n"):
        line = line.strip()
        if line and len(line) > 15 and not _LINK_RE.search(line):
            return line[:max_chars]
    return ""


def _format_duration(seconds: int) -> str:
    """Format duration as human-readable string."""
    if not seconds or seconds <= 0:
        return ""
    if seconds < 60:
        return f"{seconds}sec"
    mins = seconds // 60
    if mins < 60:
        return f"{mins}min"
    hours = mins // 60
    remaining = mins % 60
    return f"{hours}h{remaining}min"


# ── Batch prompt builder (enriched context) ───────────────────

def _build_batch_prompt(videos: List[dict]) -> str:
    """Build the user prompt for a batch of videos with enriched context."""
    lines = []
    for i, v in enumerate(videos):
        tags_raw = v.get("tags", [])
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except json.JSONDecodeError:
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []
        tags_str = ", ".join(str(t) for t in tags_list[:8])

        desc = _clean_description(v.get("description") or "")
        cat_name = CATEGORY_NAMES.get(v.get("category_id") or "", "")
        dur_str = _format_duration(v.get("duration_seconds") or 0)
        ch_desc = _clean_channel_desc(v.get("channel_description") or "")

        parts = [
            f"[{i + 1}] video_id: {v['video_id']}",
            f"    title: {v.get('title', '')}",
            f"    channel: {v.get('channel_title', '')}",
        ]
        if cat_name:
            parts.append(f"    category: {cat_name}")
        if dur_str:
            parts.append(f"    duration: {dur_str}")
        if tags_str:
            parts.append(f"    tags: {tags_str}")
        if desc:
            parts.append(f"    description: {desc}")
        if ch_desc:
            parts.append(f"    channel_about: {ch_desc}")

        lines.append("\n".join(parts))
    return "\n\n".join(lines)


# ── LLM response parser ──────────────────────────────────────

def _parse_llm_response(raw: str, video_ids: List[str]) -> Dict[str, dict]:
    """Parse the LLM JSON response into {video_id: tag_data}."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)

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


# ── LLM call (proxy + API fallback) ──────────────────────────

async def _call_proxy(prompt: str, system: str = SYSTEM_PROMPT) -> Optional[str]:
    """Call the Claude Max proxy (OpenAI-compatible endpoint)."""
    payload = {
        "model": PROXY_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(PROXY_URL, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception:
        return None


async def _call_anthropic_api(prompt: str, system: str = SYSTEM_PROMPT) -> Optional[str]:
    """Call Anthropic API directly (fallback if proxy not available)."""
    import anthropic
    settings = get_settings()
    api_key = settings.anthropic_api_key
    if not api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
        )
        return response.content[0].text
    except Exception:
        return None


async def _call_llm(prompt: str) -> Optional[str]:
    """Try proxy first, fall back to Anthropic API."""
    result = await _call_proxy(prompt)
    if result:
        return result
    return await _call_anthropic_api(prompt)


# ── Main entry point ──────────────────────────────────────────

async def tag_missing_videos(
    video_ids: List[str],
    on_progress=None,
) -> Dict[str, int]:
    """
    Tag all untagged videos via LLM (Haiku) with enriched context.

    Loads video metadata + channel description + duration for richer input.
    Uses Claude Max proxy ($0) with Anthropic API as fallback.

    Returns {"tagged": N, "already_tagged": M, "failed": F}.
    """
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

        # Load metadata with channel description and duration
        meta_rows = await conn.fetch(
            """
            SELECT vm.video_id, vm.title, vm.description, vm.channel_title,
                   vm.tags, vm.category_id, vm.duration_seconds,
                   cm.description as channel_description
            FROM video_metadata vm
            LEFT JOIN channel_metadata cm ON cm.channel_id = vm.channel_id
            WHERE vm.video_id = ANY($1)
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
                "category_id": row["category_id"],
                "duration_seconds": row["duration_seconds"],
                "channel_description": row["channel_description"],
            }

    # Only tag videos that have metadata
    taggable = [meta_map[vid] for vid in untagged if vid in meta_map]

    if not taggable:
        return {"tagged": 0, "already_tagged": len(tagged_ids), "failed": len(untagged)}

    # Batch and tag via LLM
    batches = [taggable[i:i + LLM_BATCH_SIZE] for i in range(0, len(taggable), LLM_BATCH_SIZE)]
    total_tagged = 0
    total_failed = 0

    for batch_idx, batch in enumerate(batches):
        batch_video_ids = [v["video_id"] for v in batch]
        prompt = _build_batch_prompt(batch)

        try:
            response = await _call_llm(prompt)
            if response:
                results = _parse_llm_response(response, batch_video_ids)
                if results:
                    async with get_conn() as conn:
                        for vid, tag_data in results.items():
                            try:
                                await conn.execute(
                                    """
                                    INSERT INTO video_tags (video_id, topics, domain, format, guest, model)
                                    VALUES ($1, $2, $3, $4, $5, $6)
                                    ON CONFLICT (video_id) DO NOTHING
                                    """,
                                    vid,
                                    json.dumps(tag_data["topics"]),
                                    tag_data["domain"],
                                    tag_data["format"],
                                    tag_data.get("guest"),
                                    "haiku-v3-proxy",
                                )
                            except Exception:
                                pass  # Skip FK violations for deleted videos
                    total_tagged += len(results)
                    total_failed += len(batch) - len(results)
                else:
                    total_failed += len(batch)
            else:
                total_failed += len(batch)
        except Exception:
            total_failed += len(batch)

        if on_progress:
            await on_progress(
                len(tagged_ids) + total_tagged + total_failed,
                len(video_ids),
            )

        # Small delay between batches
        if batch_idx < len(batches) - 1:
            await asyncio.sleep(0.5)

    return {
        "tagged": total_tagged,
        "already_tagged": len(tagged_ids),
        "failed": total_failed,
    }
