# ADR-007: Data Ingestion and Channel Enrichment Strategy

- **Date:** 2026-03-25
- **Status:** Proposed

## Decision

Ingest all relevant data from Google Takeout but scope v1 processing to YouTube video and channel data only. Enrich channels with lightweight LLM-generated semantic fingerprints — not broad categories — to enable matching at the right level of granularity: specific enough to avoid false positives (CoD player matched with Sims player), flexible enough to catch cross-channel affinity (two different relationship psychology channels).

## Context

The matching system (ADR-003) describes the full TF-IDF approach and the MVP (ADR-006) scopes it down to channel overlap with inverse-popularity weighting. But neither document addresses the upstream question: how does raw Takeout data become a matchable profile, and at what granularity should enrichment happen?

Two examples crystallize the problem:

1. **Call of Duty vs. The Sims** — Both are "gaming" channels. Matching at the category level would pair these users. That's a bad match. Channel-level overlap avoids this because the channels are different. But you still need to know that two *different* CoD channels represent the same interest.

2. **Relationship psychology across channels** — Someone who watches School of Life's relationship content and someone who watches a smaller relationship psychology channel don't share exact channels, but they share a meaningful interest. Pure channel overlap misses this. You need a layer that recognizes the semantic similarity without collapsing into broad categories.

The solution is a lightweight enrichment step that gives each channel a semantic fingerprint — more specific than a category, cheaper than full topic modeling.

## How It Works

### Data Ingestion

**Store everything, process selectively.** Google Takeout contains YouTube watch history, search history, subscriptions, likes, comments, and potentially data from other Google services. All of it gets stored on upload — deleting data you might need later is a one-way door. But v1 processing focuses exclusively on:

- **Watch history** — video IDs, channel IDs, timestamps, watch frequency
- **Subscriptions** — explicit channel affinity signal (stronger than a single watch)
- **Search history** — reveals intent and curiosity that passive watching doesn't capture

Other Takeout data (Google Maps, Chrome history, etc.) is stored but not processed. It's available for future enrichment if the hypothesis validates and the user consents to broader analysis.

### Channel Enrichment

Each channel gets a lightweight semantic fingerprint generated from:

- **Channel name and description**
- **Top/recent video titles** (5-10 titles capture the channel's identity well)
- **Subscriber count** (for inverse-popularity weighting per ADR-006)

An LLM generates a set of descriptive traits per channel — not a single category, but a multi-dimensional tag set. For example:

| Channel | Category (too broad) | Semantic Fingerprint (what we want) |
|---|---|---|
| TheActMan | Gaming | FPS games, game criticism, Call of Duty, gaming culture commentary |
| LilSimsie | Gaming | The Sims, cozy gaming, building/decorating, casual gameplay |
| School of Life | Education | Relationship psychology, emotional intelligence, philosophy of love |
| Heidi Priebe | Education | Attachment theory, relationship patterns, personal growth, psychology |

With fingerprints, the system can recognize that TheActMan and a CoD-focused channel share traits (FPS, Call of Duty) while TheActMan and LilSimsie do not, even though both are "gaming." It can also see that School of Life and Heidi Priebe share "relationship psychology" without needing exact channel overlap.

### Enrichment is Cached and Batched

- Channel fingerprints are generated once per channel and cached. With millions of YouTube channels but only thousands relevant to the user base, this is a bounded problem.
- New channels entering the system (from new user uploads) are enriched in batch.
- Fingerprints can be refreshed periodically as channels evolve, but this is low priority — most channels' core identity is stable.

### Profile Construction

A user's matchable profile is built from three layers:

1. **Channel set** — which channels they watch, weighted by frequency and recency (per ADR-003/006)
2. **Semantic traits** — aggregated from the fingerprints of their watched channels, weighted by how much they watch each channel. A user who watches 5 relationship psychology channels has "relationship psychology" as a strong trait even if no single channel dominates.
3. **Behavioral signals** — search history reveals active curiosity; subscription without watching reveals aspirational interests; binge patterns reveal depth vs. breadth tendencies.

Matching in v1 uses layers 1 and 2. Layer 3 is available for future refinement (ADR-004).

### Interaction Design Philosophy

The interaction model (ADR-005) describes the layers. This ADR adds a design constraint:

**Content-native, not gamified.** The word "gamified" implies mechanics — points, streaks, unlocks. What actually works is simpler: people interact with content they already care about, and someone else interacts with that interaction. That's how organic conversations start. The UX should feel like continuing a conversation that was already happening in your head, not playing a game to earn a match.

Concretely: a user sees a video or channel from their own watch history and leaves a thought. A matched user sees that thought alongside the content and responds. The content is the excuse for the conversation, not a mechanic performed for rewards.

## Consequences

- **Store-everything approach increases storage costs** but avoids irreversible data loss. Non-YouTube Takeout data can be processed later without requiring users to re-upload.
- **LLM-based fingerprinting adds a dependency and cost** but is cheap per channel (one call per channel, cached indefinitely) and far more accurate than YouTube's 15 built-in categories.
- **Semantic fingerprints enable cross-channel matching** which pure channel overlap misses. This is the key upgrade over ADR-006's minimal matching — two people interested in relationship psychology will match even if they watch different channels.
- **Fingerprint quality depends on LLM quality** — poor tagging produces poor cross-channel matching. Manual spot-checking of fingerprints is needed during early development.
- **The "not gamified" constraint limits growth mechanics** — no streaks, no points, no engagement hooks. The bet is that match quality and natural interaction drive retention better than game mechanics. This is a deliberate tradeoff.
