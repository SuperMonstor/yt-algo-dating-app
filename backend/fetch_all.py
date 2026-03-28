"""
Master pipeline runner — fetches all external data.

Usage:
    python3 fetch_all.py --api-key YOUR_API_KEY
    python3 fetch_all.py --api-key YOUR_API_KEY --skip-transcripts
    python3 fetch_all.py --api-key YOUR_API_KEY --transcripts-only --limit 100

Steps:
    1. Video metadata (YouTube Data API) — ~867 calls, ~2 min
    2. Channel metadata (YouTube Data API) — ~286 calls, ~1 min
    3. Transcripts (youtube-transcript-api) — ~4400 videos, ~37 min
"""

import os
import sys
import argparse
import subprocess


def run_step(name: str, cmd: list[str]):
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n  WARNING: {name} exited with code {result.returncode}")
        print(f"  Pipeline continues — data is saved incrementally.\n")


def main():
    parser = argparse.ArgumentParser(description="Fetch all YouTube data")
    parser.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"),
                        help="YouTube Data API v3 key")
    parser.add_argument("--skip-transcripts", action="store_true",
                        help="Skip transcript fetching (fastest run)")
    parser.add_argument("--transcripts-only", action="store_true",
                        help="Only fetch transcripts")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit transcript fetching to N videos")
    args = parser.parse_args()

    if not args.api_key and not args.transcripts_only:
        print("Error: Provide API key via --api-key or YOUTUBE_API_KEY env var")
        print("Get one free at: https://console.cloud.google.com/apis/credentials")
        print("Enable 'YouTube Data API v3' in your Google Cloud project")
        sys.exit(1)

    if not args.transcripts_only:
        # Step 1: Video metadata
        run_step("Fetching video metadata", [
            sys.executable, "fetch_video_metadata.py", "--api-key", args.api_key
        ])

        # Step 2: Channel metadata
        run_step("Fetching channel metadata", [
            sys.executable, "fetch_channel_metadata.py", "--api-key", args.api_key
        ])

    if not args.skip_transcripts:
        # Step 3: Transcripts
        cmd = [sys.executable, "fetch_transcripts.py"]
        if args.limit:
            cmd.extend(["--limit", str(args.limit)])
        run_step("Fetching transcripts (long-form only)", cmd)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")

    # Summary
    from pathlib import Path
    import json
    data_dir = Path("data")
    for f in ["video_metadata.json", "channel_metadata.json", "transcripts.json"]:
        p = data_dir / f
        if p.exists():
            with open(p) as fh:
                count = len(json.load(fh))
            size_mb = p.stat().st_size / 1024 / 1024
            print(f"  {f}: {count:,} entries ({size_mb:.1f} MB)")
        else:
            print(f"  {f}: not yet created")


if __name__ == "__main__":
    main()
