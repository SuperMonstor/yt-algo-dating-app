# ADR-008: Data Pipeline — From Takeout Upload to Matchable Profile

- **Date:** 2026-03-26
- **Status:** Accepted
- **Context:** Defines the complete processing pipeline when a user uploads their YouTube Google Takeout data — parsing, classification, enrichment, tagging, and profile generation.

## Decision

Process YouTube Takeout data through a five-stage pipeline: parse watch history, classify shorts vs long-form, enrich with YouTube API metadata, generate per-video LLM tags, and compute a matchable user profile. All enrichment is cache-first — shared across users so repeat data is never re-fetched or re-processed.

**MVP scope: Long-form content only. Shorts are discarded.** Long-form watching is deliberate — it's where identity lives. Shorts are algorithm-driven noise (~89% of watch history).

## How It Works

### Stage 1: Parse Watch History

Input: `watch-history.html` from Google Takeout.

Extract per entry:
- Video ID (from URL)
- Video title
- Channel ID and channel name
- Timestamp (when the video was watched)
- Action type (Watched / Viewed / Used — we only keep "Watched")

Also parse `subscriptions.csv` for explicit channel subscriptions.

### Stage 2: Classify Shorts vs Long-Form

YouTube takeout does not distinguish shorts from regular videos. We classify using two heuristics:

1. **Time-gap heuristic**: Entries are reverse-chronological. If the gap between watching video N and video N+1 is <90 seconds, video N is classified as a short (you couldn't have watched more than 90 seconds of it).
2. **Title hashtag**: Videos with `#shorts`, `#ytshorts`, `#short` in the title are classified as shorts.

If either is true → short. If gap >= 90 seconds → long-form. Session boundaries → unknown.

Typical result: ~89% shorts, ~11% long-form. All shorts are discarded. Only long-form video IDs proceed through the pipeline.

### Stage 3: Enrich with YouTube API (Cache-First)

For each unique long-form video ID, check the shared cache. Only fetch missing data from YouTube Data API v3.

**Video metadata** (batched 50 per API call, 1 unit each):
- title, description (truncated 500 chars), channel_id, category_id, tags, published_at
- duration_seconds, view_count, like_count, comment_count

**Channel metadata** (batched 50 per call):
- title, description, subscriber_count, video_count, view_count, country, keywords

A typical user with ~4,000 long-form videos requires ~80 video calls + ~40 channel calls = ~120 API units. Free tier allows 10,000 units/day.

### Stage 4: Per-Video LLM Tagging (Cache-First)

YouTube's built-in categories are too broad ("People & Blogs" covers everything). Creator-assigned tags are mostly channel-level, not video-specific. We use LLM tagging on title + description + channel name for fine-grained per-video classification.

**Why per-video, not per-channel:** A podcast channel like Nikhil Kamath has episodes about AI, real estate, fitness, and politics. Channel-level tagging would say "business podcast" for all episodes. Per-video tagging catches that one user watches the AI episodes and another watches the fitness episodes — they shouldn't be matched just because they share the channel.

Each video gets:
- **Topics** (3-5 specific strings): e.g. `["australian open 2026", "jannik sinner", "carlos alcaraz", "grand slam tennis finals"]`
- **Domain** (hierarchical path): e.g. `"sports > tennis > australian open"`
- **Format**: podcast, interview, tutorial, music video, documentary, vlog, comedy sketch, highlights, clip, reaction, review, explainer, news, live performance, compilation, other
- **Guest** (string or null): e.g. `"Andrew Huberman"` — critical for podcasts where the guest defines the topic

**Tagging rules:**
- Topics must be specific enough that two people could bond over them in conversation
- Never generic words like "entertainment", "content", "engagement"
- For music: artist name + genre + song reference
- For TV clips: show name + scene context
- For podcasts: discussion topic + guest name
- For sports: specific event/athlete names

**Implementation:** Batch 100 videos per LLM call. Results cached in shared `video_tags` table — never re-tagged. Cost approaches zero as user base grows and cache hit rate increases.

### Stage 5: Build User Profile

Compute the matchable profile from `{video_id: watch_count}` + shared cache data. See ADR-009 for the data model.

### Shared Cache (SQLite)

All enrichment data is stored in a shared cache so overlapping data across users is never re-processed:

| Table | Key | Data |
|-------|-----|------|
| `video_metadata` | video_id | title, description, channel_id, category_id, tags, duration, views, likes |
| `channel_metadata` | channel_id | title, subscriber_count, video_count, country, keywords |
| `video_tags` | video_id | topics[], domain, format, guest |
| `videos_not_found` | video_id | checked_at (deleted/private — skip on future lookups) |
| `channels_not_found` | channel_id | checked_at |

This is public data — properties of YouTube videos, not of users. Not user-specific, not encrypted.

### Cache-First Flow

```
New user uploads takeout
  → Parse → get video IDs
  → Filter to long-form only
  → cache.get_missing_video_ids(ids) → only fetch new from YouTube API
  → cache.get_missing_channel_ids(ids) → only fetch new channels
  → cache.get_untagged_video_ids(ids) → only LLM-tag new videos
  → Build profile from video_watches + cache
```

As user base grows, cache hit rate increases, API calls and LLM costs approach zero.

## Consequences

- **Per-video tagging is the critical differentiator** over channel-only approaches (ADR-003/007). It enables cross-channel topic matching and avoids false matches on multi-topic channels.
- **Cache-first architecture** makes the marginal cost of each new user decrease as the user base grows. The 100th user who watches the same Nikhil Kamath episode costs zero.
- **LLM tagging quality directly impacts match quality.** Tags are the "secret sauce." Poor tags → poor cross-channel matching. Spot-checking tag quality is essential.
- **Shorts classification heuristic is approximate** — some long-form videos may be misclassified if the user scrolled past quickly, and some shorts without hashtags may slip through. Acceptable for MVP; can be improved with video duration data from the API.
- **YouTube API free tier is sufficient** for MVP scale. At 10K users with 50% cache hit rate: ~60 units per user × 10K = 600K units, requiring ~60 days of quota. Manageable with staggered processing.
