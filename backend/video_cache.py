"""
SQLite cache for video and channel metadata.

Single source of truth for all fetched/processed video data.
Check cache before any API call or LLM tagging.

Usage:
    from video_cache import VideoCache
    cache = VideoCache()

    # Check before fetching
    meta = cache.get_video_metadata("dQw4w9WgXcQ")
    if not meta:
        meta = fetch_from_api("dQw4w9WgXcQ")
        cache.set_video_metadata("dQw4w9WgXcQ", meta)

    # Same for tags
    tags = cache.get_video_tags("dQw4w9WgXcQ")
    if not tags:
        tags = tag_with_llm("dQw4w9WgXcQ")
        cache.set_video_tags("dQw4w9WgXcQ", tags)
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "cache.db"


class VideoCache:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS video_metadata (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                channel_id TEXT,
                channel_title TEXT,
                category_id TEXT,
                tags TEXT,  -- JSON array
                published_at TEXT,
                duration_seconds INTEGER,
                view_count INTEGER,
                like_count INTEGER,
                comment_count INTEGER,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS channel_metadata (
                channel_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                custom_url TEXT,
                country TEXT,
                published_at TEXT,
                subscriber_count INTEGER,
                video_count INTEGER,
                view_count INTEGER,
                hidden_subscriber_count BOOLEAN,
                keywords TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS video_tags (
                video_id TEXT PRIMARY KEY,
                topics TEXT,        -- JSON array of topic strings
                domain TEXT,        -- hierarchical domain string
                format TEXT,        -- podcast, tutorial, music video, etc.
                guest TEXT,         -- guest name if applicable
                raw_response TEXT,  -- full LLM response for debugging
                model TEXT,         -- which model was used
                tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS videos_not_found (
                video_id TEXT PRIMARY KEY,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS channels_not_found (
                channel_id TEXT PRIMARY KEY,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    # ── Video Metadata ──────────────────────────────────────

    def get_video_metadata(self, video_id):
        """Returns dict or None."""
        row = self.conn.execute(
            "SELECT * FROM video_metadata WHERE video_id = ?", (video_id,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self.conn.execute("SELECT * FROM video_metadata LIMIT 0").description]
        d = dict(zip(cols, row))
        d['tags'] = json.loads(d['tags']) if d['tags'] else []
        return d

    def set_video_metadata(self, video_id, data):
        """Insert or replace video metadata."""
        tags_json = json.dumps(data.get('tags', []))
        self.conn.execute("""
            INSERT OR REPLACE INTO video_metadata
            (video_id, title, description, channel_id, channel_title, category_id,
             tags, published_at, duration_seconds, view_count, like_count, comment_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            data.get('title'),
            data.get('description'),
            data.get('channel_id'),
            data.get('channel_title'),
            data.get('category_id'),
            tags_json,
            data.get('published_at'),
            data.get('duration_seconds', 0),
            data.get('view_count', 0),
            data.get('like_count', 0),
            data.get('comment_count', 0),
        ))
        self.conn.commit()

    def set_video_metadata_batch(self, items):
        """Bulk insert video metadata. items = dict of {video_id: data}."""
        rows = []
        for video_id, data in items.items():
            rows.append((
                video_id,
                data.get('title'),
                data.get('description'),
                data.get('channel_id'),
                data.get('channel_title'),
                data.get('category_id'),
                json.dumps(data.get('tags', [])),
                data.get('published_at'),
                data.get('duration_seconds', 0),
                data.get('view_count', 0),
                data.get('like_count', 0),
                data.get('comment_count', 0),
            ))
        self.conn.executemany("""
            INSERT OR REPLACE INTO video_metadata
            (video_id, title, description, channel_id, channel_title, category_id,
             tags, published_at, duration_seconds, view_count, like_count, comment_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()

    def get_missing_video_ids(self, video_ids):
        """Returns list of video_ids not in cache (metadata or not_found)."""
        if not video_ids:
            return []
        placeholders = ",".join("?" * len(video_ids))
        cached = set(r[0] for r in self.conn.execute(
            f"SELECT video_id FROM video_metadata WHERE video_id IN ({placeholders})", video_ids
        ).fetchall())
        not_found = set(r[0] for r in self.conn.execute(
            f"SELECT video_id FROM videos_not_found WHERE video_id IN ({placeholders})", video_ids
        ).fetchall())
        return [vid for vid in video_ids if vid not in cached and vid not in not_found]

    # ── Channel Metadata ────────────────────────────────────

    def get_channel_metadata(self, channel_id):
        """Returns dict or None."""
        row = self.conn.execute(
            "SELECT * FROM channel_metadata WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self.conn.execute("SELECT * FROM channel_metadata LIMIT 0").description]
        return dict(zip(cols, row))

    def set_channel_metadata(self, channel_id, data):
        self.conn.execute("""
            INSERT OR REPLACE INTO channel_metadata
            (channel_id, title, description, custom_url, country, published_at,
             subscriber_count, video_count, view_count, hidden_subscriber_count, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            channel_id,
            data.get('title'),
            data.get('description'),
            data.get('custom_url'),
            data.get('country'),
            data.get('published_at'),
            data.get('subscriber_count', 0),
            data.get('video_count', 0),
            data.get('view_count', 0),
            data.get('hidden_subscriber_count', False),
            data.get('keywords', ''),
        ))
        self.conn.commit()

    def set_channel_metadata_batch(self, items):
        """Bulk insert channel metadata. items = dict of {channel_id: data}."""
        rows = []
        for channel_id, data in items.items():
            rows.append((
                channel_id,
                data.get('title'),
                data.get('description'),
                data.get('custom_url'),
                data.get('country'),
                data.get('published_at'),
                data.get('subscriber_count', 0),
                data.get('video_count', 0),
                data.get('view_count', 0),
                data.get('hidden_subscriber_count', False),
                data.get('keywords', ''),
            ))
        self.conn.executemany("""
            INSERT OR REPLACE INTO channel_metadata
            (channel_id, title, description, custom_url, country, published_at,
             subscriber_count, video_count, view_count, hidden_subscriber_count, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()

    def get_missing_channel_ids(self, channel_ids):
        """Returns list of channel_ids not in cache."""
        if not channel_ids:
            return []
        placeholders = ",".join("?" * len(channel_ids))
        cached = set(r[0] for r in self.conn.execute(
            f"SELECT channel_id FROM channel_metadata WHERE channel_id IN ({placeholders})", channel_ids
        ).fetchall())
        not_found = set(r[0] for r in self.conn.execute(
            f"SELECT channel_id FROM channels_not_found WHERE channel_id IN ({placeholders})", channel_ids
        ).fetchall())
        return [cid for cid in channel_ids if cid not in cached and cid not in not_found]

    # ── Video Tags (LLM) ───────────────────────────────────

    def get_video_tags(self, video_id):
        """Returns dict or None."""
        row = self.conn.execute(
            "SELECT * FROM video_tags WHERE video_id = ?", (video_id,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self.conn.execute("SELECT * FROM video_tags LIMIT 0").description]
        d = dict(zip(cols, row))
        d['topics'] = json.loads(d['topics']) if d['topics'] else []
        return d

    def set_video_tags(self, video_id, data):
        self.conn.execute("""
            INSERT OR REPLACE INTO video_tags
            (video_id, topics, domain, format, guest, raw_response, model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            json.dumps(data.get('topics', [])),
            data.get('domain'),
            data.get('format'),
            data.get('guest'),
            data.get('raw_response'),
            data.get('model'),
        ))
        self.conn.commit()

    def set_video_tags_batch(self, items):
        """Bulk insert video tags. items = dict of {video_id: data}."""
        rows = []
        for video_id, data in items.items():
            rows.append((
                video_id,
                json.dumps(data.get('topics', [])),
                data.get('domain'),
                data.get('format'),
                data.get('guest'),
                data.get('raw_response'),
                data.get('model'),
            ))
        self.conn.executemany("""
            INSERT OR REPLACE INTO video_tags
            (video_id, topics, domain, format, guest, raw_response, model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()

    def get_untagged_video_ids(self, video_ids):
        """Returns list of video_ids that don't have LLM tags yet."""
        if not video_ids:
            return []
        placeholders = ",".join("?" * len(video_ids))
        tagged = set(r[0] for r in self.conn.execute(
            f"SELECT video_id FROM video_tags WHERE video_id IN ({placeholders})", video_ids
        ).fetchall())
        return [vid for vid in video_ids if vid not in tagged]

    # ── Not Found Tracking ──────────────────────────────────

    def mark_videos_not_found(self, video_ids):
        self.conn.executemany(
            "INSERT OR IGNORE INTO videos_not_found (video_id) VALUES (?)",
            [(vid,) for vid in video_ids]
        )
        self.conn.commit()

    def mark_channels_not_found(self, channel_ids):
        self.conn.executemany(
            "INSERT OR IGNORE INTO channels_not_found (channel_id) VALUES (?)",
            [(cid,) for cid in channel_ids]
        )
        self.conn.commit()

    # ── Stats ───────────────────────────────────────────────

    def stats(self):
        counts = {}
        for table in ['video_metadata', 'channel_metadata', 'video_tags', 'videos_not_found', 'channels_not_found']:
            counts[table] = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return counts

    def close(self):
        self.conn.close()


def seed_from_json():
    """One-time import: load existing JSON data into the SQLite cache."""
    cache = VideoCache()
    data_dir = Path(__file__).parent / "data"

    # Video metadata
    vm_path = data_dir / "video_metadata.json"
    if vm_path.exists():
        with open(vm_path) as f:
            vm = json.load(f)
        cache.set_video_metadata_batch(vm)
        print(f"  Seeded {len(vm)} video metadata entries")

    # Channel metadata
    cm_path = data_dir / "channel_metadata.json"
    if cm_path.exists():
        with open(cm_path) as f:
            cm = json.load(f)
        cache.set_channel_metadata_batch(cm)
        print(f"  Seeded {len(cm)} channel metadata entries")

    # Not found videos
    nf_path = data_dir / "videos_not_found.json"
    if nf_path.exists():
        with open(nf_path) as f:
            nf = json.load(f)
        cache.mark_videos_not_found(nf)
        print(f"  Seeded {len(nf)} not-found video entries")

    print(f"\n  Cache stats: {cache.stats()}")
    print(f"  DB location: {cache.db_path}")
    cache.close()


if __name__ == "__main__":
    print("Seeding cache from existing JSON files...")
    seed_from_json()
