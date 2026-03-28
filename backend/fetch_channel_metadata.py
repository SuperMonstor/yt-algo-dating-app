"""
Fetch channel metadata using YouTube Data API v3.

Gets: subscriber count, video count, channel description, custom URL, country.
Batches 50 channel IDs per call.
Resume-friendly: skips already-fetched channels.

Usage:
    python3 fetch_channel_metadata.py --api-key YOUR_API_KEY
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
SUBSCRIPTIONS = DATA_DIR / "subscriptions.json"
OUTPUT_FILE = DATA_DIR / "channel_metadata.json"
BATCH_SIZE = 50
SLEEP_BETWEEN_BATCHES = 0.1


def load_existing_metadata() -> dict:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} existing channel metadata entries")
        return data
    return {}


def get_all_channel_ids():
    """Get unique channel IDs from watch history + subscriptions."""
    channel_ids = set()

    with open(WATCH_HISTORY, "r") as f:
        entries = json.load(f)
    for e in entries:
        if e.get("channel_id"):
            channel_ids.add(e["channel_id"])

    if SUBSCRIPTIONS.exists():
        with open(SUBSCRIPTIONS, "r") as f:
            subs = json.load(f)
        for s in subs:
            if s.get("channel_id"):
                channel_ids.add(s["channel_id"])

    return list(channel_ids)


def fetch_batch(youtube, channel_ids):
    """Fetch metadata for a batch of up to 50 channel IDs."""
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
        print(f"  API error: {e}")
        if e.resp.status == 403:
            print("  Quota exceeded! Save progress and retry tomorrow.")
    return results


def save_metadata(metadata: dict):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube channel metadata")
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"),
                        help="YouTube Data API v3 key (or set YOUTUBE_API_KEY env var)")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: Provide API key via --api-key or YOUTUBE_API_KEY env var")
        print("Get one free at: https://console.cloud.google.com/apis/credentials")
        print("Enable 'YouTube Data API v3' in your Google Cloud project")
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=args.api_key)

    metadata = load_existing_metadata()

    all_ids = get_all_channel_ids()
    remaining = [cid for cid in all_ids if cid not in metadata]
    print(f"  Total unique channels: {len(all_ids)}")
    print(f"  Already fetched: {len(metadata)}")
    print(f"  Remaining: {len(remaining)}")

    if not remaining:
        print("  All channels already fetched!")
        return

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

        for cid in batch:
            if cid not in results and cid not in metadata:
                not_found.append(cid)

        if (i + 1) % 10 == 0 or i == total_batches - 1:
            save_metadata(metadata)
            pct = (i + 1) / total_batches * 100
            print(f"  [{i+1}/{total_batches}] {pct:.0f}% — {fetched_count} fetched, {len(not_found)} not found")

        time.sleep(SLEEP_BETWEEN_BATCHES)

    save_metadata(metadata)

    print(f"\nDone!")
    print(f"  Total metadata entries: {len(metadata)}")
    print(f"  Newly fetched: {fetched_count}")
    print(f"  Not found (deleted/private): {len(not_found)}")
    print(f"  Saved to: {OUTPUT_FILE}")

    if not_found:
        nf_path = DATA_DIR / "channels_not_found.json"
        with open(nf_path, "w") as f:
            json.dump(not_found, f, indent=2)
        print(f"  Not-found list saved to: {nf_path}")


if __name__ == "__main__":
    main()
