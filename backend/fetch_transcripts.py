"""
Fetch video transcripts using youtube-transcript-api.

Fetches transcripts for long-form videos only (where signal is highest).
Resume-friendly: skips already-fetched transcripts.
Handles missing captions gracefully.

Usage:
    python3 fetch_transcripts.py
    python3 fetch_transcripts.py --all  # fetch for all videos, not just long-form
"""

import json
import sys
import time
import argparse
from typing import Optional, Tuple, Dict, Set, List
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi

DATA_DIR = Path(__file__).parent / "data"
WATCH_HISTORY = DATA_DIR / "watch_history.json"
OUTPUT_FILE = DATA_DIR / "transcripts.json"
FAILED_FILE = DATA_DIR / "transcripts_failed.json"
SLEEP_BETWEEN_REQUESTS = 0.5  # seconds, be gentle


def load_existing() -> Tuple[Dict, Set]:
    """Load already-fetched transcripts and known failures."""
    transcripts = {}
    failed = set()

    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            transcripts = json.load(f)
        print(f"  Loaded {len(transcripts)} existing transcripts")

    if FAILED_FILE.exists():
        with open(FAILED_FILE, "r") as f:
            failed = set(json.load(f))
        print(f"  Loaded {len(failed)} known failures (will skip)")

    return transcripts, failed


def get_video_ids(long_form_only=True):
    """Get unique video IDs to fetch transcripts for."""
    with open(WATCH_HISTORY, "r") as f:
        entries = json.load(f)

    if long_form_only:
        return list(set(e["video_id"] for e in entries if e["content_type"] == "long"))
    return list(set(e["video_id"] for e in entries))


YTT_API = YouTubeTranscriptApi()


def _parse_transcript(transcript, language=None):
    """Parse transcript snippets into a dict."""
    segments = []
    full_text_parts = []
    for snippet in transcript:
        segments.append({
            "start": snippet.start,
            "duration": snippet.duration,
            "text": snippet.text,
        })
        full_text_parts.append(snippet.text)

    result = {
        "full_text": " ".join(full_text_parts),
        "segment_count": len(segments),
        "duration_covered": segments[-1]["start"] + segments[-1]["duration"] if segments else 0,
    }
    if language:
        result["language"] = language
    return result


def fetch_transcript(video_id):
    """Fetch transcript for a single video. Returns None on failure."""
    try:
        transcript = YTT_API.fetch(video_id, languages=["en"])
        return _parse_transcript(transcript)
    except Exception:
        pass

    # Try any available language
    try:
        transcript_list = YTT_API.list(video_id)
        available = [t.language_code for t in transcript_list]
        if available:
            transcript = YTT_API.fetch(video_id, languages=available[:1])
            return _parse_transcript(transcript, language=available[0])
    except Exception:
        pass

    return None


def save_progress(transcripts: dict, failed: list):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(transcripts, f)  # no indent — transcripts are large
    with open(FAILED_FILE, "w") as f:
        json.dump(list(failed), f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcripts")
    parser.add_argument("--all", action="store_true",
                        help="Fetch for all videos, not just long-form")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of videos to fetch (0 = all)")
    args = parser.parse_args()

    transcripts, failed = load_existing()

    video_ids = get_video_ids(long_form_only=not args.all)
    remaining = [vid for vid in video_ids if vid not in transcripts and vid not in failed]

    if args.limit > 0:
        remaining = remaining[:args.limit]

    print(f"  Total videos to process: {len(video_ids)}", flush=True)
    print(f"  Already have transcripts: {len(transcripts)}", flush=True)
    print(f"  Known failures: {len(failed)}", flush=True)
    print(f"  Remaining to fetch: {len(remaining)}", flush=True)

    if not remaining:
        print("  Nothing to fetch!", flush=True)
        return

    print(f"  Estimated time: ~{len(remaining) * SLEEP_BETWEEN_REQUESTS / 60:.0f} minutes", flush=True)
    print(f"  Starting...\n", flush=True)

    new_fetched = 0
    new_failed = 0

    for i, vid in enumerate(remaining):
        result = fetch_transcript(vid)

        if result:
            transcripts[vid] = result
            new_fetched += 1
        else:
            failed.add(vid)
            new_failed += 1

        # Save every 20 videos
        if (i + 1) % 20 == 0 or i == len(remaining) - 1:
            save_progress(transcripts, failed)
            pct = (i + 1) / len(remaining) * 100
            print(f"  [{i+1}/{len(remaining)}] {pct:.0f}% — {new_fetched} transcripts, {new_failed} failed", flush=True)

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    save_progress(transcripts, failed)

    print(f"\nDone!", flush=True)
    print(f"  Total transcripts: {len(transcripts)}", flush=True)
    print(f"  Newly fetched: {new_fetched}", flush=True)
    print(f"  Newly failed: {new_failed}", flush=True)
    print(f"  Total failures: {len(failed)}", flush=True)
    print(f"  Saved to: {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
