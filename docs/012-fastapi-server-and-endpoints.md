# ADR-012: FastAPI Server and API Endpoints

**Date:** 2026-03-26
**Status:** Accepted

## Decision

Build the API server using FastAPI with Supabase Auth (JWT validation) for authentication. The server exposes endpoints for takeout upload, processing status, user profiles, a deep "fingerprint" view (shareable via public link), matches, and admin/health routes. The fingerprint doubles as the waitlist experience — users upload their takeout and see their YouTube personality before matching is live.

## Context

The backend data pipeline (ADR-008) processes takeout files into tagged, weighted profiles. The matching engine (ADR-010) scores user pairs. We now need an API layer that:

1. Accepts takeout uploads and orchestrates async processing
2. Serves user profiles and match results
3. Provides a compelling waitlist experience (fingerprint) before matching goes live
4. Handles auth, deletion, and health monitoring

FastAPI was chosen in ADR-002 for its async support, file upload handling, background tasks, and auto-generated docs.

## How It Works

### Authentication

- **Provider:** Supabase Auth (Google OAuth + email/password)
- **Flow:** Users authenticate via Supabase client → receive JWT → pass JWT in `Authorization: Bearer <token>` header to FastAPI
- **Validation:** FastAPI middleware validates Supabase JWTs (checks signature, expiry, issuer)
- **Linking:** Supabase `user_id` (UUID) is used as the primary key in our `users` table — no separate account system

### Endpoints

#### Public (no auth required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health: DB connection, queue depth, uptime |
| `GET` | `/stats` | Cache size (videos, channels, tags), user count, active jobs |
| `GET` | `/fingerprint/{slug}` | Public shareable fingerprint — anyone with the link can view |

#### Authenticated (Supabase JWT required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload takeout HTML. Creates user (if new) + processing job. Returns `{user_id, job_id}` |
| `POST` | `/reupload` | Upload new takeout. Additive merge per ADR-009: new videos fetched/tagged, profile recomputed |
| `GET` | `/status/{job_id}` | Poll processing job progress. Returns stage + progress details |
| `GET` | `/profile` | Authenticated user's own profile summary (top topics, channels, format breakdown) |
| `GET` | `/fingerprint` | Authenticated user's full fingerprint with shareable slug |
| `GET` | `/matches` | All matches for the authenticated user, ranked by score. Includes shared content + conversation seeds |
| `DELETE` | `/user` | Full deletion: watches, profile, index entries, matches, processing jobs. Immediate and irreversible |

### Fingerprint (Deep Dive)

The fingerprint is the centerpiece of the waitlist experience. It answers: "What does your YouTube say about you?"

**Contents:**

| Section | Data | Source |
|---------|------|--------|
| Top topics | Ranked topics with weights (e.g., "stoic philosophy: 3.2") | `user_profiles.topic_weights` |
| Top channels | Ranked channels with niche scores (lower subs = higher niche) | `user_profiles.channel_weights` × `channel_metadata` |
| Format breakdown | % podcast, tutorial, documentary, music video, etc. | `user_profiles.format_distribution` |
| Domain distribution | Hierarchical interest map (e.g., "Tech > AI > LLMs: 18%") | `user_profiles.domain_weights` |
| Watch stats | Total long-form videos, unique channels, estimated hours | `user_video_watches` × `video_metadata` |
| Most niche content | Videos/channels with lowest view/subscriber counts that the user watches | `user_video_watches` × `video_metadata` × `channel_metadata` |
| Personality type | Label derived from viewing patterns (see below) | Computed from profile |
| Shareable slug | Unique URL slug for public sharing | `users` table |

**Personality types** (derived from format distribution + topic diversity + niche depth):

| Type | Signal |
|------|--------|
| Deep Diver | Few topics, high depth per topic |
| Niche Explorer | Many niche channels (<50K subs), diverse topics |
| Polymath | High topic count across 3+ domains |
| Podcast Brain | >50% format is podcast/interview |
| Visual Learner | Heavy tutorial + explainer consumption |
| Culture Vulture | Music, film, art, literature domains dominate |

**Shareability:** Each fingerprint gets a unique slug (e.g., `/fingerprint/yt-abc123`). The public endpoint renders the same data without requiring auth. This enables social sharing — "See what YouTube thinks you are."

### Processing Job Lifecycle

When a user uploads takeout HTML:

```
POST /upload
    → Create user (if new)
    → Create processing_job (status: queued)
    → Return {user_id, job_id}
    → Background worker picks up job:
        1. parsing    — extract video IDs from HTML
        2. fetching   — fetch missing video/channel metadata from YouTube API
        3. tagging    — LLM-tag untagged videos
        4. profiling  — compute topic_weights, embedding, etc.
        5. matching   — run Stage 1 + Stage 2 against all active users
        6. done       — fingerprint + matches ready

GET /status/{job_id}
    → Returns: {status, progress: {stage, items_processed, items_total}, error}
```

### No Pagination (for now)

`GET /matches` returns all matches in a single response. At MVP scale (<1K users), this is a small payload. Pagination will be added when needed.

## Consequences

- **Waitlist-first UX** — users get value (fingerprint) before matching exists. This validates upload willingness and creates shareability.
- **Supabase coupling** — auth depends on Supabase. If we migrate away, we need to swap JWT validation but user IDs (UUIDs) remain stable.
- **Public fingerprints expose taste data** — users opt into sharing by using the public link. The fingerprint contains derived insights, not raw watch history. No video IDs or timestamps are exposed in the public view.
- **Background processing required** — upload is async. Frontend needs to poll `/status/{job_id}` or we add WebSocket support later.
- **Personality types are heuristic** — the labels are fun but not scientifically validated. They should be framed as entertainment, not assessment.
