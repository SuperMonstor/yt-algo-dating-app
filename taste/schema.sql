-- Video cache: global, shared across all users
-- Stores YouTube API metadata + LLM classifications
CREATE TABLE IF NOT EXISTS video_cache (
  video_id            TEXT PRIMARY KEY,
  title               TEXT,
  channel_name        TEXT,
  channel_id          TEXT,
  yt_category         TEXT,
  tags                JSONB DEFAULT '[]',
  description_snippet TEXT,
  classified_dimensions JSONB,
  classified_at       TIMESTAMPTZ,
  fetched_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_video_cache_channel ON video_cache (channel_id);

-- Track videos that don't exist (deleted/private) so we don't re-fetch
CREATE TABLE IF NOT EXISTS videos_not_found (
  video_id    TEXT PRIMARY KEY,
  checked_at  TIMESTAMPTZ DEFAULT now()
);

-- User profiles: the fingerprint output
CREATE TABLE IF NOT EXISTS profiles (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at        TIMESTAMPTZ DEFAULT now(),
  name              TEXT,
  email             TEXT,
  fingerprint_vector JSONB,
  hooks             JSONB,
  primary_identity  TEXT,
  guilty_pleasure   TEXT,
  dimension_labels  JSONB,
  share_slug        TEXT UNIQUE,
  video_count       INTEGER,
  top_channels      JSONB,
  raw_stats         JSONB
);

CREATE INDEX IF NOT EXISTS idx_profiles_share_slug ON profiles (share_slug);

-- Waitlist
CREATE TABLE IF NOT EXISTS waitlist (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at  TIMESTAMPTZ DEFAULT now(),
  email       TEXT UNIQUE,
  profile_id  UUID REFERENCES profiles(id)
);
