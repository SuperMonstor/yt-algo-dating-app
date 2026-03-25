# ADR-003: Matching System Design — TF-IDF Similarity on YouTube Consumption Data

- **Date:** 2026-03-24
- **Status:** Proposed

## Decision

Build the matching engine using TF-IDF weighted user vectors over YouTube channels, with cosine similarity for pairwise matching and approximate nearest neighbor (ANN) search for scale. Niche overlap is automatically amplified over broad overlap through inverse document frequency weighting — no manual curation of "what counts" is needed.

## Context

The app needs to take raw YouTube consumption data (via Google Takeout) and find other users with genuinely similar interests. The critical insight is that specificity matters: two people watching the same obscure philosophy channel is a far stronger compatibility signal than two people who both watch gaming content. The system must formalize this intuition without requiring manual categorization of what's "niche" vs. "broad."

## How It Works

### Signal Extraction

Google Takeout provides a list of watched videos with timestamps. From each video we derive:

- **Channel ID** — the most granular and reliable signal (atomic unit of matching)
- **Watch frequency per channel** — how often the user returns to a channel
- **Recency** — recent watches weighted higher than old ones
- **Temporal patterns** — depth signals like long-form vs. shorts consumption

### TF-IDF Weighting

Each user's relationship to a channel is scored using TF-IDF (Term Frequency–Inverse Document Frequency):

- **TF (Term Frequency)** — how much this user watches a given channel relative to their total consumption. Higher TF = stronger personal signal.
- **IDF (Inverse Document Frequency)** — log(total users / users who watch this channel). Channels watched by most users (e.g., MrBeast) get near-zero IDF. Channels watched by very few users (e.g., a niche continental philosophy lecturer) get high IDF.
- **Weight** = TF × IDF

This means:
- Both watching MrBeast → near-zero match signal (everyone watches it)
- Both watching Exurb1a → moderate signal (somewhat niche)
- Both watching an obscure philosophy channel → very strong signal

No manual curation is needed — IDF computes specificity from the user base automatically.

### User Vector Representation

Each user becomes a sparse vector where:
- Dimensions = all channels in the system
- Values = TF-IDF weight for that user-channel pair

Topic-level vectors are layered on top using the same TF-IDF approach at coarser granularity:

```
Level 0: Channel (most specific — "Lex Fridman")
Level 1: Sub-topic ("long-form tech interviews")
Level 2: Topic ("technology & science")
```

Channel-level matching is the primary signal. Topic-level matching provides supporting context for match explanations.

### Similarity Computation

**Cosine similarity** between user vectors is the primary metric. It measures angular distance, which normalizes for total watch volume (a 2hr/day watcher and an 8hr/day watcher can still be strong matches).

```
similarity(A, B) = dot(A, B) / (|A| × |B|)
```

The final match score is a weighted hybrid:

```
match_score =
    0.6 × cosine_similarity(channel_vectors) +
    0.25 × cosine_similarity(topic_vectors) +
    0.15 × depth_pattern_similarity
```

Where `depth_pattern_similarity` captures behavioral alignment — do they both prefer long-form content, do they both go deep on topics vs. browsing.

These weights are initial estimates and should be tuned with user feedback.

### Constellation Matching

Beyond raw similarity, the system supports three types of match signals:

1. **Shared deep interests** — Filter each user's vector to channels where TF exceeds a threshold (regular watching, not one-off). Compute overlap on this filtered set. This is the strongest signal.

2. **Adjacent curiosity** — Build a channel co-occurrence graph (channels frequently watched by the same users). Two users who don't share exact channels but share neighborhoods in this graph have adjacent curiosity. This is collaborative filtering applied to interest discovery.

3. **Complementary gaps** — User A deeply watches topic X; User B has recently started watching topic X (low TF, recent timestamps). This is a "you could learn from each other" signal. Weighted lower than direct overlap but surfaced in match explanations.

### Channel-to-Topic Mapping

Mapping channels to meaningful topic labels uses a hybrid approach:

1. **LLM classification** — Feed channel name + recent video titles to an LLM for fine-grained topic tagging. Best quality for explicit labeling.
2. **Co-occurrence clustering** — Channels frequently watched together are implicitly in the same interest space, regardless of official category. Discovers relationships that formal taxonomies miss.
3. **YouTube Data API categories** — Used as a coarse fallback only (YouTube only has ~15 categories, too broad for matching).

LLM classification for explicit labels + co-occurrence for implicit relationships is the recommended combination.

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Takeout     │────▶│  Enrichment  │────▶│  User Vector  │
│  Upload      │     │  (channel →  │     │  (TF-IDF      │
│  (JSON/HTML) │     │   topic map) │     │   sparse vec)  │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │  Vector Store  │
                                          │  (pgvector /   │
                                          │   Pinecone /   │
                                          │   Qdrant)      │
                                          └───────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │  ANN Search    │
                                          │  (top-K most   │
                                          │   similar)     │
                                          └───────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │  Re-ranking    │
                                          │  (depth, age,  │
                                          │   location)    │
                                          └───────────────┘
```

At scale, pairwise similarity is replaced with **Approximate Nearest Neighbor (ANN)** search — user vectors are stored in a vector database and queried for the top-K most similar vectors. This is O(log n) instead of O(n²).

Re-ranking applies non-content filters (location, age preferences) and boosts constellation-level signals (adjacent curiosity, complementary gaps) on top of the raw ANN results.

## Consequences

- **Niche interests are automatically amplified** — IDF handles this without manual curation, and the system improves as the user base grows (IDF becomes more accurate with more data).
- **Cold start sensitivity** — IDF weights are only meaningful with a sufficient user base. Early on, all channels appear "niche." Mitigated by seeding IDF from general YouTube channel popularity data.
- **Channel-level matching is fragile to channel changes** — If a creator rebrands or a channel is deleted, historical signals break. Mitigate by mapping to stable topic representations alongside raw channel IDs.
- **Vector dimensionality grows with channels** — Sparse vectors can have millions of dimensions. Vector databases handle this well, but the enrichment pipeline (channel → topic mapping) must keep pace with new channels entering the system.
- **Match explanations are natural** — Because matching is based on interpretable signals (shared channels, shared topics), generating human-readable "why you matched" explanations is straightforward compared to black-box embedding models.
- **Tuning is required** — The hybrid score weights (0.6/0.25/0.15) and TF thresholds for "deep interest" are starting guesses. User feedback loops (did this match lead to a conversation?) should inform tuning over time.
