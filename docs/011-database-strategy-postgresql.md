# ADR-011: Single PostgreSQL Database with pgvector

**Date:** 2026-03-26
**Status:** Accepted

## Decision

Use PostgreSQL with the pgvector extension as the single database for the entire application — replacing SQLite for the video/channel cache and serving as the store for user data, embeddings, and matching.

## Context

The backend data pipeline currently uses SQLite (`data/cache.db`) for caching video and channel metadata. As we build the FastAPI server, matching engine, and user-facing features, we need a database that handles:

- **Concurrent writes** — multiple users uploading and processing takeout files simultaneously
- **Vector similarity search** — user embeddings for Stage 2 matching
- **Inverted index queries** — Stage 1 matching ("find users who share topic X")
- **User data with privacy controls** — encrypted at rest, access control

SQLite handles the cache well but can't serve the concurrent, vector-aware, production workload. Rather than maintaining two databases (SQLite for cache + Postgres for everything else), we consolidate into a single PostgreSQL instance.

## Consequences

### Positive

- **One database to manage** — simpler deployment, backup, and monitoring
- **pgvector** — native `vector` type and similarity operators (`<=>` cosine distance) eliminate the need for a separate FAISS index
- **GIN indexes** — efficient inverted index for topic/tag-based matching queries on arrays and JSONB
- **Concurrent access** — MVCC handles multiple simultaneous uploads without blocking
- **Production-ready** — connection pooling, row-level security, encryption at rest are built-in

### Negative

- **Requires a running Postgres instance** — more setup than SQLite's single file (mitigated by Docker or managed services like Supabase/Neon)
- **Migration effort** — existing SQLite cache schema and seeding logic need to be ported to Postgres
- **Local dev setup** — developers need Postgres running locally (Docker Compose solves this)

### Migration Plan

1. Define Postgres schema covering both cache tables (video_metadata, channel_metadata, video_tags) and new user tables
2. Update `video_cache.py` to use asyncpg/psycopg instead of sqlite3
3. Port `seed_from_json()` and all cache read/write operations
4. Remove SQLite dependency and `data/cache.db`
