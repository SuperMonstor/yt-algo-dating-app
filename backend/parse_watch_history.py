"""
YouTube Watch History Parser
Parses Google Takeout watch-history.html and classifies entries as shorts vs long-form.

Classification heuristic:
- Title contains #shorts, #ytshorts, #short → short
- Time gap to next watch < 90 seconds → short
- Otherwise → long-form
"""

import re
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict

TAKEOUT_HISTORY = Path.home() / "Downloads" / "Takeout 2" / "YouTube and YouTube Music" / "history" / "watch-history.html"
TAKEOUT_SUBS = Path.home() / "Downloads" / "Takeout 4" / "YouTube and YouTube Music" / "subscriptions" / "subscriptions.csv"
TAKEOUT_COMMENTS = Path.home() / "Downloads" / "Takeout 4" / "YouTube and YouTube Music" / "comments" / "comments.csv"

OUTPUT_DIR = Path(__file__).parent / "data"

SHORTS_HASHTAGS = {"#shorts", "#ytshorts", "#short"}
SHORT_GAP_THRESHOLD_SECONDS = 90


def _parse_timestamp(text: str):
    """Try multiple timestamp formats found in Google Takeout exports."""
    # Format 1: "Jan 15, 2025, 10:30:00 AM GMT+05:30" (US locale)
    ts_match = re.search(r'(\w{3} \d+, \d{4}, \d+:\d+:\d+ [AP]M)\s*GMT', text)
    if ts_match:
        try:
            return datetime.strptime(ts_match.group(1), "%b %d, %Y, %I:%M:%S %p")
        except ValueError:
            pass

    # Format 2: "31 Dec 2025, 13:18:15" (non-US locale, 24h)
    ts_match = re.search(r'(\d{1,2} \w{3} \d{4}, \d+:\d+:\d+)', text)
    if ts_match:
        try:
            return datetime.strptime(ts_match.group(1), "%d %b %Y, %H:%M:%S")
        except ValueError:
            pass

    # Format 3: "2025-01-15T10:30:00" (ISO-ish)
    ts_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', text)
    if ts_match:
        try:
            return datetime.strptime(ts_match.group(1), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass

    return None


def _parse_html_content(content: str) -> list[dict]:
    """Parse watch-history HTML content into structured entries.

    Handles multiple Google Takeout formats:
    - Older format: <div class="outer-cell ...">
    - Newer format: <div class="content-cell mdl-cell ...">
    """
    # Try both div patterns
    raw_entries = re.findall(
        r'<div class="outer-cell.*?</div></div></div>', content, re.DOTALL
    )
    if not raw_entries:
        # Newer takeout format uses content-cell divs
        raw_entries = re.findall(
            r'<div class="content-cell[^"]*"[^>]*>.*?</div>', content, re.DOTALL
        )

    entries = []
    for entry in raw_entries:
        clean = entry.replace("\u202f", " ").replace("\xa0", " ")

        # Only keep "Watched" entries (skip Viewed, Used)
        title_match = re.search(r'Watched\s+<a href="[^"]*watch\?v=([^"&]+)">([^<]+)', clean)
        if not title_match:
            continue

        video_id = title_match.group(1)
        title = title_match.group(2)

        channel_match = re.search(r'channel/([^"]+)">([^<]+)', clean)
        channel_id = channel_match.group(1) if channel_match else None
        channel_name = channel_match.group(2) if channel_match else None

        timestamp = _parse_timestamp(clean)
        if not timestamp:
            continue

        # Check title for shorts hashtags
        title_lower = title.lower()
        has_shorts_hashtag = any(tag in title_lower for tag in SHORTS_HASHTAGS)

        entries.append({
            "video_id": video_id,
            "title": title,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "timestamp": timestamp,
            "has_shorts_hashtag": has_shorts_hashtag,
        })

    return entries


def parse_watch_history(html_path: str = TAKEOUT_HISTORY) -> list[dict]:
    """Parse watch-history.html file into structured entries."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _parse_html_content(content)


def parse_watch_history_from_string(html_content: str) -> list[dict]:
    """Parse watch-history HTML string into structured entries (for API uploads)."""
    return _parse_html_content(html_content)


def classify_shorts(entries: list[dict]) -> list[dict]:
    """Classify each entry as 'short' or 'long' using gap + hashtag heuristics.

    Entries are in reverse chronological order (newest first).
    Gap = time between current entry and the next entry watched after it.
    Since entries[i] is newer than entries[i+1], gap = entries[i].ts - entries[i+1].ts
    But what matters is: how long did the user spend on entries[i] before moving to entries[i-1]?
    gap = entries[i-1].ts - entries[i].ts
    """
    for i, entry in enumerate(entries):
        # Calculate gap: time from this video to the next video watched
        if i > 0:
            gap_seconds = (entries[i - 1]["timestamp"] - entry["timestamp"]).total_seconds()
        else:
            gap_seconds = None  # Last video in session, no next video

        entry["gap_seconds"] = gap_seconds

        # Classification
        if entry["has_shorts_hashtag"]:
            entry["content_type"] = "short"
        elif gap_seconds is not None and 0 < gap_seconds < SHORT_GAP_THRESHOLD_SECONDS:
            entry["content_type"] = "short"
        elif gap_seconds is not None and gap_seconds >= SHORT_GAP_THRESHOLD_SECONDS:
            entry["content_type"] = "long"
        else:
            entry["content_type"] = "unknown"  # session boundary or negative gap

    return entries


def parse_subscriptions(csv_path: str = TAKEOUT_SUBS) -> list[dict]:
    """Parse subscriptions CSV."""
    subs = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subs.append({
                "channel_id": row["Channel Id"],
                "channel_url": row["Channel Url"],
                "channel_name": row["Channel Title"],
            })
    return subs


def parse_comments(csv_path: str = TAKEOUT_COMMENTS) -> list[dict]:
    """Parse comments CSV."""
    comments = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text_raw = row.get("Comment Text", "")
            # Extract text from JSON wrapper
            text_match = re.search(r'"text":"(.*?)"', text_raw)
            text = text_match.group(1) if text_match else text_raw

            comments.append({
                "comment_id": row["Comment ID"],
                "video_id": row["Video ID"],
                "timestamp": row["Comment Create Timestamp"],
                "text": text,
            })
    return comments


def generate_profile(entries: list[dict]) -> dict:
    """Generate a user profile summary from classified watch history."""
    total = len(entries)
    shorts = [e for e in entries if e["content_type"] == "short"]
    longs = [e for e in entries if e["content_type"] == "long"]

    # Channel frequency for long-form only (high signal)
    long_channel_counts = Counter(e["channel_name"] for e in longs if e["channel_name"])
    short_channel_counts = Counter(e["channel_name"] for e in shorts if e["channel_name"])
    all_channel_counts = Counter(e["channel_name"] for e in entries if e["channel_name"])

    # Unique channels
    long_channels = set(e["channel_id"] for e in longs if e["channel_id"])
    short_channels = set(e["channel_id"] for e in shorts if e["channel_id"])

    # Time range
    timestamps = [e["timestamp"] for e in entries]
    earliest = min(timestamps)
    latest = max(timestamps)

    # Yearly breakdown
    yearly = defaultdict(lambda: {"short": 0, "long": 0, "unknown": 0})
    for e in entries:
        year = e["timestamp"].year
        yearly[year][e["content_type"]] += 1

    profile = {
        "total_entries": total,
        "shorts_count": len(shorts),
        "long_count": len(longs),
        "shorts_pct": round(len(shorts) / total * 100, 1) if total else 0,
        "long_pct": round(len(longs) / total * 100, 1) if total else 0,
        "unique_channels_long": len(long_channels),
        "unique_channels_short": len(short_channels),
        "date_range": f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}",
        "top_30_long_channels": long_channel_counts.most_common(30),
        "top_30_short_channels": short_channel_counts.most_common(30),
        "top_30_all_channels": all_channel_counts.most_common(30),
        "yearly_breakdown": dict(sorted(yearly.items())),
    }

    return profile


def save_outputs(entries: list[dict], profile: dict, subs: list[dict], comments: list[dict]):
    """Save parsed data and profile to files."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Save entries as JSON (convert datetime to string)
    entries_out = []
    for e in entries:
        out = {**e, "timestamp": e["timestamp"].isoformat()}
        entries_out.append(out)

    with open(OUTPUT_DIR / "watch_history.json", "w") as f:
        json.dump(entries_out, f, indent=2)

    # Save profile
    with open(OUTPUT_DIR / "profile.json", "w") as f:
        json.dump(profile, f, indent=2, default=str)

    # Save subscriptions
    with open(OUTPUT_DIR / "subscriptions.json", "w") as f:
        json.dump(subs, f, indent=2)

    # Save comments
    with open(OUTPUT_DIR / "comments.json", "w") as f:
        json.dump(comments, f, indent=2)

    print(f"Saved {len(entries_out)} watch entries to {OUTPUT_DIR / 'watch_history.json'}")
    print(f"Saved profile to {OUTPUT_DIR / 'profile.json'}")
    print(f"Saved {len(subs)} subscriptions to {OUTPUT_DIR / 'subscriptions.json'}")
    print(f"Saved {len(comments)} comments to {OUTPUT_DIR / 'comments.json'}")


def print_profile(profile: dict):
    """Print a human-readable profile summary."""
    print("\n" + "=" * 60)
    print("YOUTUBE PROFILE SUMMARY")
    print("=" * 60)
    print(f"Date range: {profile['date_range']}")
    print(f"Total watched: {profile['total_entries']:,}")
    print(f"  Shorts: {profile['shorts_count']:,} ({profile['shorts_pct']}%)")
    print(f"  Long-form: {profile['long_count']:,} ({profile['long_pct']}%)")
    print(f"Unique channels (long-form): {profile['unique_channels_long']:,}")
    print(f"Unique channels (shorts): {profile['unique_channels_short']:,}")

    print("\n--- Yearly Breakdown ---")
    for year, counts in profile["yearly_breakdown"].items():
        total_yr = sum(counts.values())
        print(f"  {year}: {total_yr:>6,} total | {counts['long']:>5,} long | {counts['short']:>5,} short")

    print("\n--- Top 30 Long-Form Channels ---")
    for i, (ch, count) in enumerate(profile["top_30_long_channels"], 1):
        print(f"  {i:>2}. {ch:<45} {count:>5} watches")

    print("\n--- Top 30 Shorts Channels ---")
    for i, (ch, count) in enumerate(profile["top_30_short_channels"], 1):
        print(f"  {i:>2}. {ch:<45} {count:>5} watches")


if __name__ == "__main__":
    print("Parsing watch history...")
    entries = parse_watch_history()
    print(f"  Parsed {len(entries)} watched video entries")

    print("Classifying shorts vs long-form...")
    entries = classify_shorts(entries)

    print("Parsing subscriptions...")
    subs = parse_subscriptions()
    print(f"  Found {len(subs)} subscriptions")

    print("Parsing comments...")
    comments = parse_comments()
    print(f"  Found {len(comments)} comments")

    print("Generating profile...")
    profile = generate_profile(entries)

    save_outputs(entries, profile, subs, comments)
    print_profile(profile)
