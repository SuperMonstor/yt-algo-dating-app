"""
Process a new user's YouTube takeout data.

Pipeline:
    1. Parse watch history HTML
    2. Classify shorts vs long-form
    3. Filter to long-form only
    4. Check cache for existing video/channel metadata
    5. Fetch only what's missing from YouTube API
    6. Check cache for existing LLM tags
    7. Tag only untagged videos with LLM
    8. Build user profile

Usage:
    python3 process_user.py --history PATH_TO_WATCH_HISTORY_HTML --api-key YOUR_KEY
    python3 process_user.py --history ~/Downloads/Takeout/YouTube*/history/watch-history.html --api-key YOUR_KEY
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from video_cache import VideoCache
from parse_watch_history import parse_watch_history, classify_shorts
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 0.1


def parse_duration(iso_duration):
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def fetch_video_batch(youtube, video_ids):
    results = {}
    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids),
        ).execute()
        for item in response.get("items", []):
            vid = item["id"]
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            stats = item.get("statistics", {})
            results[vid] = {
                "title": snippet.get("title"),
                "description": snippet.get("description", "")[:500],
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "category_id": snippet.get("categoryId"),
                "tags": snippet.get("tags", []),
                "published_at": snippet.get("publishedAt"),
                "duration_seconds": parse_duration(content.get("duration", "")),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            }
    except HttpError as e:
        print(f"  API error (videos): {e}", flush=True)
    return results


def fetch_channel_batch(youtube, channel_ids):
    results = {}
    try:
        response = youtube.channels().list(
            part="snippet,statistics,brandingSettings",
            id=",".join(channel_ids),
        ).execute()
        for item in response.get("items", []):
            cid = item["id"]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            branding = item.get("brandingSettings", {}).get("channel", {})
            results[cid] = {
                "title": snippet.get("title"),
                "description": snippet.get("description", "")[:500],
                "custom_url": snippet.get("customUrl"),
                "country": snippet.get("country"),
                "published_at": snippet.get("publishedAt"),
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
                "view_count": int(stats.get("viewCount", 0)),
                "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
                "keywords": branding.get("keywords", ""),
            }
    except HttpError as e:
        print(f"  API error (channels): {e}", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Process a user's YouTube takeout")
    parser.add_argument("--history", required=True, help="Path to watch-history.html")
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"),
                        help="YouTube Data API v3 key")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip API fetching (use cache only)")
    args = parser.parse_args()

    cache = VideoCache()

    # ── Step 1: Parse watch history ──────────────────────
    print("Step 1: Parsing watch history...", flush=True)
    entries = parse_watch_history(args.history)
    print(f"  Parsed {len(entries)} video entries", flush=True)

    # ── Step 2: Classify shorts vs long-form ─────────────
    print("Step 2: Classifying shorts vs long-form...", flush=True)
    entries = classify_shorts(entries)
    total_short = sum(1 for e in entries if e['content_type'] == 'short')
    total_long = sum(1 for e in entries if e['content_type'] == 'long')
    total_unknown = sum(1 for e in entries if e['content_type'] == 'unknown')
    print(f"  Long-form: {total_long} | Shorts: {total_short} | Unknown: {total_unknown}", flush=True)

    # ── Step 3: Filter to long-form only ─────────────────
    print("Step 3: Filtering to long-form only...", flush=True)
    long_entries = [e for e in entries if e['content_type'] == 'long']
    long_video_ids = list(set(e['video_id'] for e in long_entries))
    long_channel_ids = list(set(e['channel_id'] for e in long_entries if e['channel_id']))
    print(f"  Unique long-form videos: {len(long_video_ids)}", flush=True)
    print(f"  Unique long-form channels: {len(long_channel_ids)}", flush=True)

    # ── Step 4: Check cache, fetch missing ───────────────
    if not args.skip_fetch:
        if not args.api_key:
            print("  Warning: No API key provided. Skipping fetch.", flush=True)
        else:
            youtube = build("youtube", "v3", developerKey=args.api_key)

            # Videos
            missing_vids = cache.get_missing_video_ids(long_video_ids)
            print(f"\nStep 4a: Video metadata", flush=True)
            print(f"  Cached: {len(long_video_ids) - len(missing_vids)}", flush=True)
            print(f"  Need to fetch: {len(missing_vids)}", flush=True)

            if missing_vids:
                batches = [missing_vids[i:i+BATCH_SIZE] for i in range(0, len(missing_vids), BATCH_SIZE)]
                fetched = 0
                not_found = []
                for i, batch in enumerate(batches):
                    results = fetch_video_batch(youtube, batch)
                    if results:
                        cache.set_video_metadata_batch(results)
                        fetched += len(results)
                    for vid in batch:
                        if vid not in results:
                            not_found.append(vid)
                    if (i + 1) % 10 == 0 or i == len(batches) - 1:
                        print(f"  [{i+1}/{len(batches)}] {fetched} fetched, {len(not_found)} not found", flush=True)
                    time.sleep(SLEEP_BETWEEN_BATCHES)
                if not_found:
                    cache.mark_videos_not_found(not_found)
                print(f"  Done: {fetched} new, {len(not_found)} not found", flush=True)

            # Channels
            missing_chs = cache.get_missing_channel_ids(long_channel_ids)
            print(f"\nStep 4b: Channel metadata", flush=True)
            print(f"  Cached: {len(long_channel_ids) - len(missing_chs)}", flush=True)
            print(f"  Need to fetch: {len(missing_chs)}", flush=True)

            if missing_chs:
                batches = [missing_chs[i:i+BATCH_SIZE] for i in range(0, len(missing_chs), BATCH_SIZE)]
                fetched = 0
                not_found = []
                for i, batch in enumerate(batches):
                    results = fetch_channel_batch(youtube, batch)
                    if results:
                        cache.set_channel_metadata_batch(results)
                        fetched += len(results)
                    for cid in batch:
                        if cid not in results:
                            not_found.append(cid)
                    if (i + 1) % 10 == 0 or i == len(batches) - 1:
                        print(f"  [{i+1}/{len(batches)}] {fetched} fetched, {len(not_found)} not found", flush=True)
                    time.sleep(SLEEP_BETWEEN_BATCHES)
                if not_found:
                    cache.mark_channels_not_found(not_found)
                print(f"  Done: {fetched} new, {len(not_found)} not found", flush=True)

    # ── Step 5: Check which videos need LLM tagging ──────
    untagged = cache.get_untagged_video_ids(long_video_ids)
    print(f"\nStep 5: LLM tagging status", flush=True)
    print(f"  Already tagged: {len(long_video_ids) - len(untagged)}", flush=True)
    print(f"  Need tagging: {len(untagged)}", flush=True)
    # LLM tagging will be a separate script (tag_videos.py)

    # ── Summary ──────────────────────────────────────────
    stats = cache.stats()
    print(f"\n{'='*50}", flush=True)
    print(f"  PROCESSING COMPLETE", flush=True)
    print(f"{'='*50}", flush=True)
    print(f"  User's long-form videos:  {len(long_video_ids)}", flush=True)
    print(f"  User's long-form channels:{len(long_channel_ids)}", flush=True)
    print(f"  Cache — videos:           {stats['video_metadata']}", flush=True)
    print(f"  Cache — channels:         {stats['channel_metadata']}", flush=True)
    print(f"  Cache — tagged:           {stats['video_tags']}", flush=True)
    print(f"  Videos needing LLM tags:  {len(untagged)}", flush=True)
    if untagged:
        print(f"\n  Next step: python3 tag_videos.py --api-key YOUR_OPENAI_KEY", flush=True)

    cache.close()


if __name__ == "__main__":
    main()
