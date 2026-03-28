"""
Tag long-form videos with topics, domain, format, and guest using an LLM.

Reads from the SQLite cache, tags untagged videos, writes back to cache.
Batches 20 videos per LLM call to reduce cost.
Resume-friendly: skips already-tagged videos.

Usage:
    python3 tag_videos.py --api-key YOUR_OPENAI_KEY
    python3 tag_videos.py --api-key YOUR_OPENAI_KEY --limit 100
    python3 tag_videos.py --api-key YOUR_OPENAI_KEY --model gpt-4o-mini
    # or set OPENAI_API_KEY env var
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from video_cache import VideoCache

BATCH_SIZE = 20
SLEEP_BETWEEN_CALLS = 0.5

SYSTEM_PROMPT = """You are a video content tagger. Given a batch of YouTube videos (title, channel, tags, description), classify each one.

For each video, return:
- topics: 3-5 specific topic tags (lowercase, e.g. "sleep science", "startup funding", "tennis highlights")
- domain: hierarchical category (e.g. "self-improvement > health > sleep", "sports > tennis", "tech > AI")
- format: one of: podcast, interview, tutorial, music video, documentary, vlog, comedy sketch, highlights, clip, reaction, review, explainer, news, live performance, compilation, other
- guest: name of the guest if it's an interview/podcast and you can identify them from the title/description, otherwise null

Return ONLY a JSON array with one object per video, in the same order as input. Each object must have keys: video_id, topics, domain, format, guest.

Be specific with topics — "artificial intelligence" is better than "technology". "marathon training" is better than "fitness"."""


def build_batch_prompt(videos):
    """Build the user prompt for a batch of videos."""
    lines = []
    for i, (vid, meta) in enumerate(videos):
        tags_str = ", ".join(meta.get('tags', [])[:8]) if meta.get('tags') else ""
        desc = (meta.get('description') or '')[:200].replace('\n', ' ')
        lines.append(
            f"[{i+1}] video_id: {vid}\n"
            f"    title: {meta.get('title', '')}\n"
            f"    channel: {meta.get('channel_title', '')}\n"
            f"    tags: {tags_str}\n"
            f"    description: {desc}"
        )
    return "\n\n".join(lines)


def call_llm(api_key, model, system_prompt, user_prompt):
    """Call Anthropic API and return the response text."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
        )
        return response.content[0].text
    except Exception as e:
        print(f"  API error: {e}", flush=True)
        return None


def parse_llm_response(raw_response, video_ids):
    """Parse the LLM JSON response into a dict of {video_id: tag_data}."""
    try:
        data = json.loads(raw_response)
        # Handle both {"results": [...]} and direct [...]
        if isinstance(data, dict):
            items = data.get("results", data.get("videos", []))
            if not items:
                # Maybe it's {video_id: {...}, ...}
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
                                "raw_response": raw_response,
                            }
                    return results
                # Try first list-like value
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
                    "raw_response": raw_response,
                }
        return results
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  Parse error: {e}", flush=True)
        return {}


def main():
    parser = argparse.ArgumentParser(description="Tag videos with LLM")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"),
                        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        help="Model to use (default: claude-haiku-4-5-20251001)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of videos to tag (0 = all)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"Videos per LLM call (default: {BATCH_SIZE})")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: Provide API key via --api-key or OPENAI_API_KEY env var")
        sys.exit(1)

    cache = VideoCache()

    # Get all long-form video IDs from watch history
    data_dir = Path(__file__).parent / "data"
    with open(data_dir / "watch_history.json") as f:
        history = json.load(f)
    long_video_ids = list(set(e['video_id'] for e in history if e['content_type'] == 'long'))

    # Find untagged
    untagged = cache.get_untagged_video_ids(long_video_ids)
    if args.limit > 0:
        untagged = untagged[:args.limit]

    print(f"Total long-form videos: {len(long_video_ids)}", flush=True)
    print(f"Already tagged: {len(long_video_ids) - len(cache.get_untagged_video_ids(long_video_ids))}", flush=True)
    print(f"To tag this run: {len(untagged)}", flush=True)
    print(f"Model: {args.model}", flush=True)
    print(f"Batch size: {args.batch_size}", flush=True)

    if not untagged:
        print("Nothing to tag!", flush=True)
        cache.close()
        return

    # Build batches of (video_id, metadata) pairs
    batches = []
    current_batch = []
    for vid in untagged:
        meta = cache.get_video_metadata(vid)
        if meta:
            current_batch.append((vid, meta))
        if len(current_batch) >= args.batch_size:
            batches.append(current_batch)
            current_batch = []
    if current_batch:
        batches.append(current_batch)

    print(f"Batches: {len(batches)}", flush=True)
    print(f"Videos with metadata: {sum(len(b) for b in batches)}", flush=True)
    print(f"Videos without metadata (skipped): {len(untagged) - sum(len(b) for b in batches)}", flush=True)
    print(flush=True)

    total_tagged = 0
    total_failed = 0

    for i, batch in enumerate(batches):
        video_ids = [vid for vid, _ in batch]
        prompt = build_batch_prompt(batch)
        raw = call_llm(args.api_key, args.model, SYSTEM_PROMPT, prompt)

        if raw:
            results = parse_llm_response(raw, video_ids)
            if results:
                # Add model info
                for vid in results:
                    results[vid]["model"] = args.model
                cache.set_video_tags_batch(results)
                total_tagged += len(results)
            else:
                total_failed += len(batch)
        else:
            total_failed += len(batch)

        if (i + 1) % 5 == 0 or i == len(batches) - 1:
            pct = (i + 1) / len(batches) * 100
            print(f"  [{i+1}/{len(batches)}] {pct:.0f}% — {total_tagged} tagged, {total_failed} failed", flush=True)

        time.sleep(SLEEP_BETWEEN_CALLS)

    stats = cache.stats()
    print(f"\nDone!", flush=True)
    print(f"  Newly tagged: {total_tagged}", flush=True)
    print(f"  Failed: {total_failed}", flush=True)
    print(f"  Total tagged in cache: {stats['video_tags']}", flush=True)
    cache.close()


if __name__ == "__main__":
    main()
