-- YT Algo Dating App — PostgreSQL Schema
-- Requires: CREATE EXTENSION vector;  (pgvector)

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- CACHE LAYER (public video/channel data — migrated from SQLite)
-- ============================================================

CREATE TABLE video_metadata (
    video_id       TEXT PRIMARY KEY,
    title          TEXT,
    description    TEXT,
    channel_id     TEXT,
    channel_title  TEXT,
    category_id    TEXT,
    tags           JSONB DEFAULT '[]',
    published_at   TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0,
    view_count     BIGINT DEFAULT 0,
    like_count     BIGINT DEFAULT 0,
    comment_count  BIGINT DEFAULT 0,
    fetched_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_video_channel ON video_metadata (channel_id);

CREATE TABLE channel_metadata (
    channel_id            TEXT PRIMARY KEY,
    title                 TEXT,
    description           TEXT,
    custom_url            TEXT,
    country               TEXT,
    published_at          TIMESTAMPTZ,
    subscriber_count      BIGINT DEFAULT 0,
    video_count           INTEGER DEFAULT 0,
    view_count            BIGINT DEFAULT 0,
    hidden_subscriber_count BOOLEAN DEFAULT FALSE,
    keywords              TEXT,
    fetched_at            TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE video_tags (
    video_id      TEXT PRIMARY KEY REFERENCES video_metadata(video_id),
    topics        JSONB DEFAULT '[]',
    domain        TEXT,
    format        TEXT,
    guest         TEXT,
    raw_response  TEXT,
    model         TEXT,
    tagged_at     TIMESTAMPTZ DEFAULT now()
);

-- GIN index on topics array for fast "which videos have topic X" lookups
CREATE INDEX idx_video_tags_topics ON video_tags USING GIN (topics);
CREATE INDEX idx_video_tags_domain ON video_tags (domain);

CREATE TABLE videos_not_found (
    video_id    TEXT PRIMARY KEY,
    checked_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE channels_not_found (
    channel_id  TEXT PRIMARY KEY,
    checked_at  TIMESTAMPTZ DEFAULT now()
);


-- ============================================================
-- USER DATA
-- ============================================================

CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    last_upload_at  TIMESTAMPTZ,
    status          TEXT DEFAULT 'pending'  -- pending | processing | active | deleted
);

CREATE INDEX idx_users_status ON users (status);

-- Source of truth: what did this user watch and how many times?
-- ~4,000 rows per user, ~120 KB per user (from ADR-009)
CREATE TABLE user_video_watches (
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    video_id    TEXT NOT NULL,
    watch_count INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, video_id)
);

CREATE INDEX idx_watches_video ON user_video_watches (video_id);


-- ============================================================
-- USER PROFILE (derived, fully recomputable from watches + cache)
-- ============================================================

CREATE TABLE user_profiles (
    user_id              UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,

    -- Weighted maps (derived from video_watches × video_tags × IDF)
    topic_weights        JSONB DEFAULT '{}',     -- {topic: weight}
    channel_weights      JSONB DEFAULT '{}',     -- {channel_id: weight}
    domain_weights       JSONB DEFAULT '{}',     -- {domain: weight}
    format_distribution  JSONB DEFAULT '{}',     -- {format: proportion}, sums to 1.0

    -- 384-dim vector from sentence-transformers (all-MiniLM-L6-v2)
    embedding            vector(384),

    total_long_form_videos INTEGER DEFAULT 0,
    computed_at          TIMESTAMPTZ DEFAULT now()
);

-- pgvector index for fast cosine similarity in Stage 2
-- Using ivfflat; switch to hnsw at >100K users
CREATE INDEX idx_profile_embedding ON user_profiles USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ============================================================
-- GLOBAL INDICES (for Stage 1 candidate retrieval)
-- ============================================================

-- Inverted index: topic → users who have that topic
CREATE TABLE topic_user_index (
    topic       TEXT NOT NULL,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    weight      REAL NOT NULL,  -- user's topic_weight for this topic
    PRIMARY KEY (topic, user_id)
);

CREATE INDEX idx_topic_user_userid ON topic_user_index (user_id);

-- Inverted index: channel → users who watch that channel
CREATE TABLE channel_user_index (
    channel_id  TEXT NOT NULL,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    weight      REAL NOT NULL,  -- user's channel_weight for this channel
    PRIMARY KEY (channel_id, user_id)
);

CREATE INDEX idx_channel_user_userid ON channel_user_index (user_id);

-- Precomputed IDF and niche scores (updated when user base changes)
CREATE TABLE global_stats (
    key         TEXT PRIMARY KEY,  -- 'topic_idf', 'channel_niche', 'total_users'
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);


-- ============================================================
-- MATCHES
-- ============================================================

CREATE TABLE matches (
    user_id_a       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_id_b       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    score           REAL NOT NULL,
    score_a_to_b    REAL NOT NULL,
    score_b_to_a    REAL NOT NULL,

    -- Breakdown for explainability
    topic_overlap   REAL,
    embedding_sim   REAL,
    channel_overlap REAL,
    domain_sim      REAL,
    format_sim      REAL,
    complementary   REAL,

    -- Match context (for conversation seeds + "why you matched")
    details         JSONB,   -- shared_channels, shared_topics, conversation_seed, etc.

    computed_at     TIMESTAMPTZ DEFAULT now(),

    PRIMARY KEY (user_id_a, user_id_b),
    CHECK (user_id_a < user_id_b)  -- canonical ordering, no duplicates
);

CREATE INDEX idx_matches_user_a ON matches (user_id_a, score DESC);
CREATE INDEX idx_matches_user_b ON matches (user_id_b, score DESC);


-- ============================================================
-- PROCESSING JOBS (for async takeout upload tracking)
-- ============================================================

CREATE TABLE processing_jobs (
    job_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status      TEXT DEFAULT 'queued',  -- queued | parsing | fetching | tagging | profiling | matching | done | failed
    progress    JSONB DEFAULT '{}',     -- {stage: "fetching", videos_processed: 120, videos_total: 400}
    error       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_user ON processing_jobs (user_id, created_at DESC);
CREATE INDEX idx_jobs_status ON processing_jobs (status);
