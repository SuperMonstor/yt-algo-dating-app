# YT Algo Dating App — Backend

Match people based on YouTube long-form consumption patterns. The core thesis: shared niche content consumption signals compatibility better than self-reported preferences.

## Architecture

```
Upload HTML → parse → fetch (YouTube API) → tag (Claude Haiku) → profile → match
```

- **FastAPI** server with async endpoints
- **PostgreSQL + pgvector** for storage, embeddings, and inverted index lookups
- **Supabase Auth** (ES256 JWT) for authentication
- **sentence-transformers** (all-MiniLM-L6-v2) for 384-dim user embeddings
- **Two-stage matching**: inverted index retrieval → multi-signal scoring

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 15+ with [pgvector](https://github.com/pgvector/pgvector)
- Docker (for test database)

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set up the database

```bash
# Create database
psql postgresql://postgres:postgres@localhost:5432 -c "CREATE DATABASE ytalgo;"

# Apply schema (includes pgvector extension)
psql postgresql://postgres:postgres@localhost:5432/ytalgo -f schema.sql
```

### 3. Configure environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ytalgo

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWK={"x":"...","y":"...","alg":"ES256","crv":"P-256","kty":"EC","key_ops":["verify"]}

YOUTUBE_API_KEY=your-youtube-data-api-v3-key
ANTHROPIC_API_KEY=your-anthropic-api-key  # optional, for LLM tagging
```

### 4. Run the server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Server runs at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## API Endpoints

### Public (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check (DB status, uptime) |
| `GET` | `/stats` | User count, cached videos/channels/tags, active jobs |
| `GET` | `/fingerprint/{slug}` | Public shareable fingerprint |

### Authenticated (Supabase JWT in `Authorization: Bearer <token>`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload `watch-history.html` from Google Takeout |
| `POST` | `/reupload` | Additive re-upload (merges with existing data) |
| `GET` | `/status/{job_id}` | Poll processing job progress |
| `GET` | `/profile` | Your profile (top topics, channels, format breakdown) |
| `GET` | `/fingerprint` | Your full fingerprint with shareable slug |
| `GET` | `/matches` | Your matches with scores and conversation seeds |
| `DELETE` | `/user` | Delete all your data (irreversible) |

## Usage Examples

### Upload takeout

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@watch-history.html"
```

Response:
```json
{"user_id": "aaa-bbb-ccc", "job_id": "ddd-eee-fff"}
```

### Poll status

```bash
curl http://localhost:8000/status/ddd-eee-fff \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "status": "fetching",
  "progress": {"stage": "fetching", "items_processed": 120, "items_total": 400}
}
```

Stages: `queued` → `parsing` → `fetching` → `tagging` → `profiling` → `matching` → `done`

### View fingerprint

```bash
curl http://localhost:8000/fingerprint \
  -H "Authorization: Bearer $TOKEN"
```

Response includes:
- Top topics with weights
- Top channels with subscriber counts
- Format breakdown (% podcast, tutorial, etc.)
- Domain distribution (music, sports, tech, etc.)
- Most niche channels and videos
- Personality type (Polymath, Deep Diver, Podcast Brain, etc.)
- Shareable slug for public link

### View matches

```bash
curl http://localhost:8000/matches \
  -H "Authorization: Bearer $TOKEN"
```

Each match includes:
- Overall score + per-direction scores
- Score breakdown (topic overlap, embedding similarity, channel overlap, domain, format, complementary gaps)
- Shared topics and channels
- Complementary topics ("you could learn from each other")
- Conversation seed with a specific video prompt

### Terminal fingerprint viewer

```bash
python3 show_fingerprint.py
```

Renders a beautiful terminal UI of the fingerprint with colored bars, stats, and hidden gems.

## Processing Pipeline

When a user uploads their Google Takeout `watch-history.html`:

1. **Parse** — Extract video IDs, channels, timestamps. Classify shorts vs long-form (shorts discarded).
2. **Fetch** — Batch-fetch missing video + channel metadata from YouTube Data API v3 (50 per call).
3. **Tag** — LLM-tag untagged videos with topics, domain, format, guest (20 per batch via Claude Haiku).
4. **Profile** — Compute topic/channel/domain weights, format distribution, 384-dim embedding.
5. **Match** — Stage 1 inverted index retrieval (top 2000 candidates) → Stage 2 multi-signal scoring.

## Matching Algorithm

Six signals, weighted per [ADR-010](../docs/010-matching-architecture-and-algorithm.md):

| Signal | Weight | Description |
|--------|--------|-------------|
| Topic overlap | 35% | Shared topics weighted by min weight, normalized |
| Embedding similarity | 25% | Cosine similarity of 384-dim user vectors |
| Channel overlap | 20% | Shared channels weighted by niche score (low subs = high value) |
| Domain hierarchy | 10% | Shared prefix levels in hierarchical domains |
| Format similarity | 5% | Cosine similarity of format distributions |
| Complementary gaps | 5% | One user deep, other exploring same topic |

Final score uses harmonic mean of both directions to handle asymmetry.

## Testing

Tests run against a real PostgreSQL container with pgvector.

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run all 68 tests
python3 -m pytest tests/ -v
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, lifespan, CORS
│   ├── config.py            # Settings from .env
│   ├── database.py          # asyncpg connection pool
│   ├── auth.py              # Supabase ES256 JWT validation
│   ├── models.py            # Pydantic request/response schemas
│   ├── routes/
│   │   ├── health.py        # GET /health, /stats
│   │   ├── upload.py        # POST /upload, /reupload
│   │   ├── status.py        # GET /status/{job_id}
│   │   ├── profile.py       # GET /profile
│   │   ├── fingerprint.py   # GET /fingerprint, /fingerprint/{slug}
│   │   ├── matches.py       # GET /matches
│   │   └── user.py          # DELETE /user
│   └── services/
│       ├── pipeline.py      # Background processing orchestration
│       ├── fetcher.py       # Async YouTube API fetcher
│       ├── tagger.py        # Async LLM video tagger
│       ├── profile.py       # Profile computation + embeddings
│       └── matching.py      # Two-stage matching engine
├── schema.sql               # PostgreSQL schema (pgvector)
├── docker-compose.test.yml  # Test database container
├── show_fingerprint.py      # Terminal fingerprint viewer
├── requirements.txt
└── tests/                   # 68 integration tests
```

## ADRs

Architecture decisions are documented in `docs/`:

- [ADR-008](../docs/008-data-pipeline-takeout-to-profile.md) — Data pipeline
- [ADR-009](../docs/009-per-user-data-model-and-privacy.md) — Per-user data model and privacy
- [ADR-010](../docs/010-matching-architecture-and-algorithm.md) — Matching architecture
- [ADR-011](../docs/011-database-strategy-postgresql.md) — PostgreSQL with pgvector
- [ADR-012](../docs/012-fastapi-server-and-endpoints.md) — FastAPI server and endpoints
