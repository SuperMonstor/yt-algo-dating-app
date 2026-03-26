"""
Fetch video metadata from YouTube Data API v3.

Gets: duration, view count, like count, category, tags, description, channel ID.
Batches 50 video IDs per API call (1 unit each = very efficient).
Resume-friendly: skips already-fetched videos.

Usage:
    python3 fetch_video_metadata.py --api-key YOUR_API_KEY
    # or set YOUTUBE_API_KEY env var
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DATA_DIR = Path(__file__).parent / "data"
WATCH_HISTORY = DATA_DIR / "watch_history.json"
OUTPUT_FILE = DATA_DIR / "video_metadata.json"
BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 0.1  # seconds, gentle rate limiting


def load_existing_metadata() -> dict:
    """Load already-fetched metadata to enable resuming."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} existing video metadata entries")
        return data
    return {}


def get_all_video_ids():
    """Get unique video IDs from watch history."""
    with open(WATCH_HISTORY, "r") as f:
        entries = json.load(f)
    return list(set(e["video_id"] for e in entries))


def parse_duration(iso_duration: str) -> int:
    """Convert ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def fetch_batch(youtube, video_ids):
    """Fetch metadata for a batch of up to 50 video IDs."""
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
                "description": snippet.get("description", "")[:500],  # truncate long descriptions
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "category_id": snippet.get("categoryId"),
                "tags": snippet.get("tags", []),
                "published_at": snippet.get("publishedAt"),
                "duration_iso": content.get("duration"),
                "duration_seconds": parse_duration(content.get("duration", "")),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
            }

    except HttpError as e:
        print(f"  API error: {e}")
        if e.resp.status == 403:
            print("  Quota exceeded! Save progress and retry tomorrow.")
            return results

    return results


def save_metadata(metadata: dict):
    """Save metadata to file."""
    with open(OUTPUT_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video metadata")
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"),
                        help="YouTube Data API v3 key (or set YOUTUBE_API_KEY env var)")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: Provide API key via --api-key or YOUTUBE_API_KEY env var")
        print("Get one free at: https://console.cloud.google.com/apis/credentials")
        print("Enable 'YouTube Data API v3' in your Google Cloud project")
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=args.api_key)

    # Load existing progress
    metadata = load_existing_metadata()

    # Get video IDs to fetch
    all_ids = get_all_video_ids()
    remaining = [vid for vid in all_ids if vid not in metadata]
    print(f"  Total unique videos: {len(all_ids)}")
    print(f"  Already fetched: {len(metadata)}")
    print(f"  Remaining: {len(remaining)}")

    if not remaining:
        print("  All videos already fetched!")
        return

    # Batch fetch
    batches = [remaining[i:i + BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"  Fetching in {total_batches} batches of {BATCH_SIZE}...")
    print(f"  Estimated API units: {total_batches} (daily limit: 10,000)")

    fetched_count = 0
    not_found = []

    for i, batch in enumerate(batches):
        results = fetch_batch(youtube, batch)
        metadata.update(results)
        fetched_count += len(results)

        # Track videos not found (deleted/private)
        found_ids = set(results.keys())
        for vid in batch:
            if vid not in found_ids and vid not in metadata:
                not_found.append(vid)

        # Save every 10 batches
        if (i + 1) % 10 == 0 or i == total_batches - 1:
            save_metadata(metadata)
            pct = (i + 1) / total_batches * 100
            print(f"  [{i+1}/{total_batches}] {pct:.0f}% — {fetched_count} fetched, {len(not_found)} not found")

        time.sleep(SLEEP_BETWEEN_BATCHES)

    # Final save
    save_metadata(metadata)

    print(f"\nDone!")
    print(f"  Total metadata entries: {len(metadata)}")
    print(f"  Newly fetched: {fetched_count}")
    print(f"  Not found (deleted/private): {len(not_found)}")
    print(f"  Saved to: {OUTPUT_FILE}")

    # Save not-found list for reference
    if not_found:
        nf_path = DATA_DIR / "videos_not_found.json"
        with open(nf_path, "w") as f:
            json.dump(not_found, f, indent=2)
        print(f"  Not-found list saved to: {nf_path}")


if __name__ == "__main__":
    main()
