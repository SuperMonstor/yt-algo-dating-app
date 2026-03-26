# ADR-009: Per-User Data Model and Privacy

- **Date:** 2026-03-26
- **Status:** Accepted
- **Context:** Defines what data is stored per user, what is discarded, and how privacy is maintained. Directly addresses the tension between matching quality and data minimization.

## Decision

Store exactly one thing per user: `{video_id: watch_count}` for their long-form videos. Everything else — topic weights, channel weights, embeddings, format distributions — is derived from this + the shared cache and can be recomputed at any time. Raw takeout HTML is processed in memory and never stored. Timestamps and watch order are used during processing for temporal decay and shorts classification, then discarded.

## How It Works

### What We Store Per User

**Source of truth:**
```
video_watches: {video_id: watch_count}
```
~4,000 entries, ~120 KB per user. This is the only raw user data we persist.

**Derived profile (cached computation, fully recomputable):**

| Field | Description | Derived From |
|---|---|---|
| `topic_weights` | Each topic scored by frequency × IDF × temporal_decay | video_watches × video_tags × global IDF |
| `channel_weights` | Each channel scored by watch count × niche score | video_watches × channel_metadata |
| `channel_fingerprints` | Per-channel topic summary (top topics, primary domain, main format) | video_watches × video_tags grouped by channel |
| `domain_weights` | Distribution across hierarchical domains | video_watches × video_tags |
| `format_distribution` | Proportion of podcasts, music videos, tutorials, etc. (sums to 1.0) | video_watches × video_tags |
| `embedding` | 384-dim vector (weighted avg of topic embeddings via sentence-transformer) | topic_weights × topic_embeddings |
| `total_long_form_videos` | Count | video_watches |

### What We Never Store

| Data | Why Not |
|---|---|
| Raw takeout HTML | Processed in memory, never touches disk. Most sensitive piece — contains full history with timestamps |
| Timestamps / watch order | Used during processing for temporal decay and shorts classification, then discarded |
| Shorts data | Classified and discarded during pipeline Stage 2 |
| Video titles or descriptions | These live in the shared cache (public data), not per-user storage |

### Temporal Decay

During initial processing, timestamps are used to apply exponential decay before being discarded:

```
temporal_weight = exp(-lambda × days_since_last_watched)
```

Recent watching counts more than old watching. Half-life is ~6 months (tunable). This is baked into topic_weights and channel_weights at profile computation time.

### Re-Upload Handling

On re-upload:
1. Parse new takeout → get new long-form video IDs with counts
2. Diff against stored `video_watches` → identify new videos
3. Fetch metadata + tag only new videos (cache-first)
4. Merge new video_watches with existing (update counts, add new entries)
5. Recompute derived profile

The user doesn't lose their existing data — re-uploads are additive.

### Recomputability

If we change the tagging algorithm, weighting formula, or decay parameter:
1. Per-video tags live in the shared cache — re-tag if needed
2. User's `video_watches` are the source of truth
3. Recompute all derived profiles from `video_watches × cache`
4. No re-upload required

This is why `video_watches` is the right primitive — it's stable across algorithm changes.

### Data Separation

| Layer | Data | User-Specific? | Encrypted? |
|---|---|---|---|
| Shared cache | video_metadata, channel_metadata, video_tags | No — properties of videos | No — public data |
| User data | video_watches | Yes | AES-256 at rest |
| User profile | topic_weights, embedding, etc. | Yes | AES-256 at rest |

### User Controls

- **View profile**: Users can see what we derived from their data (topic breakdown, channel list, personality signals)
- **Delete all data**: Removes video_watches, derived profile, and entries from all indices. Immediate and complete.
- **Re-upload**: Additive merge with existing data. Refreshes temporal weights.

## Consequences

- **Minimal attack surface** — a breach exposes video IDs with watch counts, not timestamped viewing history. Video IDs are public identifiers; the mapping of "which user watched which videos" is the sensitive part.
- **Full recomputability** — algorithm improvements don't require user action. We can re-tag, re-weight, and re-embed without re-uploads.
- **Lost temporal granularity** — after initial processing, we lose the ability to re-analyze time-of-day patterns, session behavior, or interest evolution. These can only be refreshed on re-upload.
- **Storage is small** — ~120 KB per user for video_watches + ~480 KB for derived profile. At 100K users: ~60 GB total. Manageable on a single disk.
- **Diverges from ADR-007's "store everything" approach** — ADR-007 recommends storing raw takeout and other Google data for future use. This ADR prioritizes data minimization. The tradeoff: we lose the option to process Chrome history or Maps data later, but we dramatically reduce breach liability.
