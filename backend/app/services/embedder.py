"""
Video embedding service.

Embeds videos using sentence-transformers (all-MiniLM-L6-v2, 384 dims).
Runs locally, free, ~1000 videos/sec on CPU.

Also handles cluster assignment using pre-trained KMeans centroids.
"""

import json
import math
import numpy as np
from pathlib import Path
from uuid import UUID
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer

from app.database import get_conn

MODEL_DIR = Path(__file__).resolve().parent / "model_data"
CENTROIDS_PATH = MODEL_DIR / "cluster_centroids.npy"
CLUSTER_LABELS_PATH = MODEL_DIR / "cluster_labels.json"

# Lazy-loaded model
_model = None
_centroids = None
_cluster_labels = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_centroids():
    global _centroids
    if _centroids is None and CENTROIDS_PATH.exists():
        _centroids = np.load(str(CENTROIDS_PATH))
    return _centroids


def _get_cluster_labels() -> dict:
    global _cluster_labels
    if _cluster_labels is None and CLUSTER_LABELS_PATH.exists():
        with open(CLUSTER_LABELS_PATH) as f:
            _cluster_labels = json.load(f)
    return _cluster_labels or {}


def _clean_description(desc: str, max_chars: int = 150) -> str:
    """Strip boilerplate from YouTube description."""
    if not desc:
        return ""
    lines = desc.split("\n")
    clean = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if "http" in line or "@" in line.lower():
            continue
        if any(w in line.lower() for w in ["subscribe", "follow me", "business inquir"]):
            break
        clean.append(line)
    return " ".join(clean)[:max_chars]


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of texts into 384-dim vectors."""
    model = _get_model()
    return model.encode(texts, show_progress_bar=False, batch_size=256)


def assign_clusters(embeddings: np.ndarray) -> np.ndarray:
    """Assign embeddings to nearest pre-trained cluster centroid."""
    centroids = _get_centroids()
    if centroids is None:
        return np.full(len(embeddings), -1, dtype=np.int32)
    # Nearest centroid via dot product (assumes L2-normalized)
    similarities = embeddings @ centroids.T
    return np.argmax(similarities, axis=1)


async def embed_missing_videos(video_ids: List[str], on_progress=None) -> Dict[str, int]:
    """
    Embed videos that don't have embeddings yet.
    Builds text from: title + channel + cleaned description + creator tags.
    Stores embeddings in video_embeddings table.
    """
    # Check which videos already have embeddings
    async with get_conn() as conn:
        existing = await conn.fetch(
            "SELECT video_id FROM video_embeddings WHERE video_id = ANY($1)",
            video_ids,
        )
        existing_ids = {r["video_id"] for r in existing}
        need_embed = [vid for vid in video_ids if vid not in existing_ids]

        if not need_embed:
            if on_progress:
                await on_progress(len(video_ids), len(video_ids))
            return {"embedded": 0, "already_cached": len(existing_ids)}

        # Load metadata for videos that need embedding
        rows = await conn.fetch(
            """
            SELECT vm.video_id, vm.title, vm.channel_title, vm.description, vm.tags
            FROM video_metadata vm
            WHERE vm.video_id = ANY($1)
            """,
            need_embed,
        )

    # Build text for each video
    texts = []
    vid_order = []
    for r in rows:
        title = r["title"] or ""
        channel = r["channel_title"] or ""
        desc = _clean_description(r["description"] or "")

        tags_raw = r["tags"]
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except json.JSONDecodeError:
                tags = []
        elif isinstance(tags_raw, list):
            tags = tags_raw
        else:
            tags = []
        tags_str = ", ".join(str(t) for t in tags[:5])

        text = f"{title}. {channel}. {tags_str}. {desc}".strip()
        texts.append(text)
        vid_order.append(r["video_id"])

    if not texts:
        return {"embedded": 0, "already_cached": len(existing_ids)}

    # Embed
    embeddings = embed_texts(texts)

    # Assign clusters
    cluster_ids = assign_clusters(embeddings)

    # Store in DB
    async with get_conn() as conn:
        for i, vid in enumerate(vid_order):
            emb = embeddings[i]
            cid = int(cluster_ids[i]) if cluster_ids[i] >= 0 else None
            emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
            try:
                await conn.execute(
                    """
                    INSERT INTO video_embeddings (video_id, embedding, cluster_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (video_id) DO NOTHING
                    """,
                    vid, emb_str, cid,
                )
            except Exception:
                pass

    if on_progress:
        await on_progress(len(video_ids), len(video_ids))

    return {"embedded": len(vid_order), "already_cached": len(existing_ids)}


async def compute_user_fingerprint(user_id: UUID) -> dict:
    """
    Compute the full fingerprint for a user from raw data + embeddings.
    No LLM tags required.

    Returns the juicy fingerprint dict ready for API response.
    """
    async with get_conn() as conn:
        # Get everything we need in one query
        rows = await conn.fetch(
            """
            SELECT uvw.video_id, uvw.watch_count,
                   vm.title, vm.channel_title, vm.category_id,
                   vm.duration_seconds, vm.view_count,
                   cm.title as ch_name, cm.subscriber_count,
                   ve.cluster_id
            FROM user_video_watches uvw
            JOIN video_metadata vm ON vm.video_id = uvw.video_id
            LEFT JOIN channel_metadata cm ON cm.channel_id = vm.channel_id
            LEFT JOIN video_embeddings ve ON ve.video_id = uvw.video_id
            WHERE uvw.user_id = $1
            """,
            user_id,
        )

    if not rows:
        return None

    total_watches = sum(r["watch_count"] for r in rows)

    # ── Channel stats ──
    ch_watches = {}
    ch_subs = {}
    for r in rows:
        cn = r["ch_name"] or r["channel_title"] or "Unknown"
        ch_watches[cn] = ch_watches.get(cn, 0) + r["watch_count"]
        if cn not in ch_subs:
            ch_subs[cn] = r["subscriber_count"] or 0
    unique_channels = len(ch_watches)

    # ── Duration stats ──
    total_seconds = sum((r["duration_seconds"] or 0) * r["watch_count"] for r in rows)
    total_hours = round(total_seconds / 3600, 1)
    long_videos = sum(1 for r in rows if (r["duration_seconds"] or 0) > 1800)

    # ── Cluster weights (interest DNA) ──
    cluster_weights = {}
    for r in rows:
        cid = r["cluster_id"]
        if cid is not None:
            cluster_weights[cid] = cluster_weights.get(cid, 0) + r["watch_count"]

    cluster_labels = _get_cluster_labels()
    cluster_total = sum(cluster_weights.values()) or 1

    interest_dna = []
    for cid, weight in sorted(cluster_weights.items(), key=lambda x: x[1], reverse=True)[:12]:
        cid_str = str(cid)
        label = cluster_labels.get(cid_str, {}).get("label", f"cluster {cid}")
        category = cluster_labels.get(cid_str, {}).get("category", "other")
        pct = round(weight / cluster_total * 100, 1)
        interest_dna.append({"label": label, "category": category, "percentage": pct})

    # ── Top channels (non-music) ──
    top_channels = []
    for cn, count in sorted(ch_watches.items(), key=lambda x: x[1], reverse=True):
        top_channels.append({
            "name": cn,
            "watch_count": count,
            "subscriber_count": ch_subs.get(cn, 0),
        })

    # Filter non-music for interest channels
    interest_channels = []
    for r in rows:
        if r["category_id"] == "10":
            continue
        cn = r["ch_name"] or r["channel_title"] or "Unknown"
        found = next((c for c in interest_channels if c["name"] == cn), None)
        if found:
            found["watch_count"] += r["watch_count"]
        else:
            interest_channels.append({
                "name": cn,
                "watch_count": r["watch_count"],
                "subscriber_count": ch_subs.get(cn, 0),
            })
    interest_channels.sort(key=lambda x: x["watch_count"], reverse=True)

    # ── Niche channels (< 100K subs, watched 3+) ──
    niche_channels = [
        {"name": cn, "watch_count": count, "subscriber_count": ch_subs[cn]}
        for cn, count in ch_watches.items()
        if 1000 < ch_subs.get(cn, 0) < 100000 and count >= 3
    ]
    niche_channels.sort(
        key=lambda x: x["watch_count"] * math.log(100000 / max(x["subscriber_count"], 1)),
        reverse=True,
    )

    # ── Comfort content (rewatched 3+) ──
    comfort_content = sorted(
        [{"title": r["title"], "watch_count": r["watch_count"],
          "channel": r["ch_name"] or r["channel_title"]}
         for r in rows if r["watch_count"] >= 3],
        key=lambda x: x["watch_count"],
        reverse=True,
    )

    # ── Depth vs breadth ──
    deep_channels = sum(1 for _, c in ch_watches.items() if c >= 10)
    one_off_pct = round(sum(1 for _, c in ch_watches.items() if c == 1) / max(unique_channels, 1) * 100)

    # ── Archetype (exclude music — it dominates but isn't identity) ──
    cat_weights = {}
    for item in interest_dna[:10]:
        if item["category"] != "music":
            cat_weights[item["category"]] = cat_weights.get(item["category"], 0) + item["percentage"]
    top_cat = max(cat_weights, key=cat_weights.get) if cat_weights else "explorer"

    archetypes = {
        "sports": {"label": "The Endurance Junkie", "description": "You don't just watch sports. You study technique, obsess over gear, and train like a pro."},
        "self-improvement": {"label": "The Optimizer", "description": "Philosophy, psychology, habits. You're reverse-engineering being human."},
        "comedy": {"label": "The Culture Sponge", "description": "If it's funny, you've seen it. From sitcoms to stand-up to viral sketches."},
        "business": {"label": "The Builder", "description": "Startups, crypto, finance. You see the world in systems and opportunities."},
        "tech": {"label": "The Tech Mind", "description": "AI, dev tools, science. You build things and understand how things work."},
        "entertainment": {"label": "The Binge Watcher", "description": "TV, film, and pop culture are your domain. You always know what to watch next."},
        "education": {"label": "The Knowledge Seeker", "description": "Lectures, explainers, courses. YouTube is your university."},
        "gaming": {"label": "The Gamer", "description": "Whether it's walkthroughs, esports, or indie gems — gaming is your world."},
        "lifestyle": {"label": "The Lifestyle Explorer", "description": "Fashion, travel, food, vlogs — you're curating a life worth living."},
        "music": {"label": "The Music Soul", "description": "Your taste in music runs deep. From mainstream bangers to obscure finds."},
    }
    archetype = archetypes.get(top_cat, {"label": "The Explorer", "description": "Your taste defies easy labels."})

    return {
        "archetype": archetype,
        "stats": {
            "total_videos": total_watches,
            "unique_channels": unique_channels,
            "total_hours": total_hours,
            "total_days": round(total_hours / 24, 1),
        },
        "interest_dna": interest_dna,
        "obsessed_channels": interest_channels[:8],
        "niche_channels": niche_channels[:5],
        "comfort_content": comfort_content[:5],
        "watch_personality": {
            "deep_channels": deep_channels,
            "one_off_percentage": one_off_pct,
            "long_form_count": long_videos,
            "niche_count": len(niche_channels),
        },
    }
