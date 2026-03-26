"""
Pydantic models for API request/response schemas.
"""

from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


# ── Upload ────────────────────────────────────────────────

class UploadResponse(BaseModel):
    user_id: UUID
    job_id: UUID


# ── Processing Status ─────────────────────────────────────

class JobProgress(BaseModel):
    stage: Optional[str] = None
    items_processed: int = 0
    items_total: int = 0

class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress: JobProgress
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Profile ───────────────────────────────────────────────

class ProfileResponse(BaseModel):
    user_id: UUID
    top_topics: List[Dict]         # [{topic, weight}]
    top_channels: List[Dict]       # [{channel_id, title, weight, subscriber_count}]
    format_distribution: Dict      # {format: proportion}
    domain_weights: Dict           # {domain: weight}
    total_long_form_videos: int
    computed_at: Optional[datetime]


# ── Fingerprint ───────────────────────────────────────────

class FingerprintResponse(BaseModel):
    user_id: UUID
    slug: str
    top_topics: List[Dict]
    top_channels: List[Dict]
    format_distribution: Dict
    domain_distribution: Dict
    watch_stats: Dict              # {total_videos, unique_channels, estimated_hours}
    most_niche_channels: List[Dict]
    most_niche_videos: List[Dict]
    personality_type: Dict         # {label, description}
    computed_at: Optional[datetime]


# ── Matches ───────────────────────────────────────────────

class MatchResponse(BaseModel):
    match_user_id: UUID
    score: float
    score_breakdown: Dict
    shared_topics: List[Dict]
    shared_channels: List[Dict]
    complementary_topics: List[Dict]
    conversation_seed: Optional[Dict]


class MatchListResponse(BaseModel):
    user_id: UUID
    matches: List[MatchResponse]
    total: int


# ── Health / Stats ────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    uptime_seconds: float

class StatsResponse(BaseModel):
    users: int
    active_users: int
    videos_cached: int
    channels_cached: int
    videos_tagged: int
    active_jobs: int
