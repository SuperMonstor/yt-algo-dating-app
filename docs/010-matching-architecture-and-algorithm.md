# ADR-010: Matching Architecture and Algorithm

- **Date:** 2026-03-26
- **Status:** Accepted
- **Context:** Defines how users are matched — the data structures, the two-stage retrieval and ranking pipeline, the scoring formula, and the match output format. Builds on ADR-003's TF-IDF foundation while adding per-video topic matching, semantic embeddings, complementary gap detection, and conversation seed generation.

## Decision

Use a hybrid two-stage matching architecture: fast candidate retrieval via inverted index (Stage 1), followed by detailed multi-signal scoring (Stage 2). This is the same pattern used by Spotify, Netflix, and YouTube in production. Each match is returned with explanations and a conversation seed — the "why you matched" and "what to talk about" are first-class outputs, not afterthoughts.

## Context

ADR-003 established TF-IDF over channels as the core matching approach. This ADR extends it with:
- **Per-video topic matching** (enabled by ADR-008's LLM tagging) — catches cross-channel interest overlap
- **Semantic embedding similarity** — catches near-matches ("marathon training" ≈ "ultramarathon")
- **Complementary gap detection** — surfaces "you could learn from each other" pairs
- **Conversation seeds** — every match comes with a shared content prompt, implementing the "ideas before people" principle from ADR-005

## How It Works

### Data Structures

#### Per-User (from ADR-009)
```
topic_weights:     dict[topic → float]       # ~12K entries
channel_weights:   dict[channel_id → float]   # ~2K entries
domain_weights:    dict[domain → float]
format_distribution: dict[format → float]     # sums to 1.0
embedding:         float[384]                 # sentence-transformer vector
```

#### Global Indices (in memory, maintained across all users)
```
topic_to_users:    dict[topic → set[user_id]]         # inverted index
channel_to_users:  dict[channel_id → set[user_id]]    # inverted index
topic_idf:         dict[topic → float]                 # log(N / users_with_topic)
channel_niche:     dict[channel_id → float]            # log(max_subs / subs)
topic_embedding:   dict[topic → float[384]]            # sentence-transformer, cached
```

### Stage 1: Candidate Retrieval

Find users who share topics/channels with the query user. IDF weighting ensures niche overlaps surface first.

```
Input: query_user
Output: top 2000 candidates with coarse scores

For each topic in query_user.topic_weights:
    candidates = topic_to_users[topic]
    for candidate in candidates:
        coarse_score[candidate] += topic_idf[topic] × query_user.topic_weights[topic]

For each channel in query_user.channel_weights:
    candidates = channel_to_users[channel]
    for candidate in candidates:
        coarse_score[candidate] += channel_niche[channel]

Return top 2000 by coarse_score
```

Time: O(T × avg_users_per_topic). At 10K users: ~10-50ms.

### Stage 2: Fine Ranking

For each candidate, compute a multi-signal similarity score:

```
score = (
    0.35 × topic_overlap_score     +
    0.25 × embedding_cosine_sim    +
    0.20 × channel_overlap_score   +
    0.10 × domain_hierarchy_score  +
    0.05 × format_similarity_score +
    0.05 × complementary_gap_score
)
```

**Topic overlap score (35%)**
```
shared = query.topics ∩ candidate.topics
score = Σ idf[t] × min(query.weight[t], candidate.weight[t]) for t in shared
```
IDF weighting means a shared niche topic like "solana defi" scores exponentially higher than a shared generic topic.

**Embedding cosine similarity (25%)**
```
score = dot(query.embedding, candidate.embedding) / (|query| × |candidate|)
```
Catches semantic near-matches that exact topic matching misses. "marathon training" and "ultramarathon running" have high cosine similarity even though they're different topic strings.

**Channel overlap score (20%)**
```
shared = query.channels ∩ candidate.channels
score = Σ log(max_subs / subs[ch]) × engagement_factor(ch) for ch in shared
```
A shared 5K-sub channel scores ~4x higher than a shared 5M-sub channel. This is the core thesis — niche overlap = real compatibility.

**Domain hierarchy score (10%)**
```
Count shared prefix levels between domain strings:
"sports > tennis > equipment" vs "sports > tennis > australian open" → 2 shared levels
"sports > tennis" vs "sports > cycling" → 1 shared level
```
Captures abstract interest alignment even when specific topics differ.

**Format similarity score (5%)**
```
score = cosine_similarity(query.format_dist, candidate.format_dist)
```
Both prefer podcasts over tutorials? Higher score.

**Complementary gap score (5%)**
```
For each topic in both users' profiles:
    a = query.topic_weights[topic]
    b = candidate.topic_weights[topic]
    if max(a,b) / min(a,b) > 5:  # one much deeper than the other
        gap_score += idf[topic] × log(max(a,b) / min(a,b))
```
Detects when User A is deep in a topic and User B is just exploring it. "You could learn from each other."

### Asymmetry Handling

Match quality may differ per direction (A is a great match for B's interests, but not vice versa):
```
final = 2 × score_A→B × score_B→A / (score_A→B + score_B→A)
```

### Match Output

Every match returns actionable context, not just a number:

```json
{
    "match_user_id": "user_456",
    "score": 0.82,
    "shared_niche_channels": [
        {"name": "Ben Johnson", "subs": 22100, "niche_weight": 1.7}
    ],
    "shared_topics": [
        {"topic": "stoic philosophy", "idf": 3.2},
        {"topic": "zone 2 training", "idf": 2.8}
    ],
    "shared_niche_videos": [
        {"video_id": "abc123", "title": "Qban Exchange Founders", "views": 3}
    ],
    "complementary_topics": [
        {"topic": "solana defi", "you": "deep", "them": "exploring"}
    ],
    "conversation_seed": {
        "video_id": "xyz789",
        "title": "How Can People Become A Morning Person? | Andrew Huberman",
        "channel": "Chris Williamson",
        "prompt": "You both follow Chris Williamson. What did you think of his take on morning routines with Huberman?"
    }
}
```

**Conversation seed generation:** For each match, pick the best shared content to start a conversation:
1. Find shared channels with highest combined engagement
2. Pick a specific video from that channel (prefer recent, high-engagement)
3. Generate a prompt referencing the shared interest

This implements the "ideas before people" principle from ADR-005 at the API level.

### Signal Tiers

| Tier | Signal | Rationale |
|------|--------|-----------|
| S | Shared niche channel (<50K subs), both watch long-form | Core thesis |
| S | Shared niche video (<10K views) both watched | Both found the same obscure content |
| A | Shared long-form channel with high engagement depth | Deliberate overlap |
| A | Shared topic across different channels (IDF-weighted) | Same interest, different discovery path |
| A | High embedding similarity (>0.85 cosine) | Deeply similar taste |
| B | Domain distribution similarity | Abstract alignment |
| B | Complementary depth (one deep, one exploring) | "Learn from each other" |
| C | Shared mainstream channel (>1M subs) | Everyone watches these |
| D | Format / behavioral similarity | Lifestyle tiebreaker |

**Minimum threshold:** 1 S-tier signal OR 2 A-tier signals to surface a match.

### Relationship to ADR-003

This ADR extends ADR-003 rather than replacing it:
- **Adopts:** TF-IDF weighting, cosine similarity, inverse-popularity, the principle that IDF handles niche amplification automatically
- **Extends:** Adds per-video topic matching (not just channels), semantic embeddings, complementary gaps, conversation seeds
- **Modifies scoring weights:** ADR-003 proposed 0.6/0.25/0.15 (channel/topic/depth). This ADR uses 0.35/0.25/0.20/0.10/0.05/0.05 (topic/embedding/channel/domain/format/complementary) — shifting primary weight from channel to topic because per-video tagging enables much richer topic signals

### Scaling

| Scale | Stage 1 | Stage 2 | Query Time |
|---|---|---|---|
| 1K-10K | Inverted index (Python dicts) | Weighted formula | <50ms |
| 10K-100K | FAISS HNSW + inverted index | Same formula | <30ms |
| 100K+ | FAISS IVF-PQ | Learned ranker (LightGBM) | <20ms |

## Consequences

- **Match quality depends on tag quality** — the 35% topic overlap score and 25% embedding score both derive from LLM tags. Bad tags → bad matches. ADR-008's tagging rules are critical.
- **Scoring weights are initial estimates** — 0.35/0.25/0.20/0.10/0.05/0.05 should be tuned with user feedback (ADR-004's refinement loop, when built).
- **Complementary gaps add discovery** — beyond "you both like X," matches can surface "they're an expert in X, you're just getting into it." This is a different kind of value than pure overlap.
- **Conversation seeds make matches actionable** — the frontend doesn't need to invent conversation starters. The API provides them. This directly implements ADR-005's Layer 1 (Sparks) at the backend level.
- **Full pairwise matching at small scale** — with <1K users, skip Stage 1 and score all pairs. O(n²) is fine at small scale and produces exact results (no approximation from ANN).
- **Cold start for IDF** — with very few users, all topics look "niche" (IDF is high for everything). Mitigate by seeding IDF from YouTube video view counts as a proxy for topic popularity until the user base is large enough.
