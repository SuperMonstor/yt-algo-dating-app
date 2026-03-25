# ADR-006: MVP Scope — Minimum Viable Matching

- **Date:** 2026-03-25
- **Status:** Proposed

## Decision

The MVP is exactly three things: upload Takeout data, find people with strong niche channel overlap, and seed a conversation around shared content. Nothing else ships until the core hypothesis is validated — that people who share niche YouTube taste actually enjoy talking to each other.

## Context

Early conversations exploring the app concept (matching via YouTube consumption, content-first interactions, continuous refinement) generated a rich set of ideas documented across ADR-003 through ADR-005. However, the risk of building toward the full vision too early is high. The matching system design (ADR-003) includes TF-IDF vectors, topic modeling, constellation matching, and ANN search. The interaction model (ADR-005) describes three layers of content-first interaction. The refinement loop (ADR-004) adds behavioral feedback and re-upload cycles.

None of that matters if the foundational hypothesis is wrong. The MVP must test one thing: does shared niche YouTube consumption predict conversational compatibility?

Additionally, the app will launch with a small user base. This is a feature, not a bug — it allows computationally expensive, high-quality approaches that don't scale but produce better matches when every match needs to count.

## What Ships

### Matching (Simplified ADR-003)

- **Channel overlap with inverse-popularity weighting.** For each shared channel between two users, score it as `1 / log(subscriber_count)` and sum. Rank pairs by that score. No embeddings, no topic modeling, no complementary-interest logic.
- **Full pairwise similarity.** With a small user base, compute all-pairs matching directly. No ANN search needed yet — this is O(n^2) but affordable at small scale and produces exact results.
- **Opinionated output.** Fewer, higher-confidence suggestions rather than a large pool of mediocre ones. The algorithm should be selective because each match needs to land.

### Interaction (Simplified ADR-005)

- **One shared video as conversation seed.** When two people are matched, pick a video from a channel they both watch. Show it to person A with a simple prompt ("what do you think about this?"). Person B sees the video and person A's thought, and can respond.
- **No swiping, no "you matched!" notifications, no confetti.** The conversation should feel like it started in the middle — like overhearing someone say something interesting and jumping in.
- **No takes, no rabbit holes, no system-generated sparks.** Launch with Layer 1 only (a single seeded prompt per match), validate that it produces real conversations, then layer in complexity.

### Data Pipeline

- **Takeout upload and channel extraction.** Parse Google Takeout watch history, extract channel IDs and watch frequency.
- **Channel metadata enrichment.** Pull subscriber counts via YouTube Data API for inverse-popularity weighting.
- **No topic mapping, no LLM classification, no co-occurrence clustering.** These are ADR-003 features for later.

## What Does NOT Ship

- Topic-level vectors or topic modeling (ADR-003 Levels 1-2)
- Constellation matching: adjacent curiosity, complementary gaps (ADR-003)
- Takes or user-generated content (ADR-005 Layer 2)
- Shared rabbit hole detection (ADR-005 Layer 3)
- Behavioral feedback refinement loop (ADR-004)
- Re-upload nudges (ADR-004)
- Temporal decay (ADR-004)
- Location or age filtering
- Profile pages beyond minimal identity

## Success Criteria

The MVP validates the core hypothesis if:

1. **Matches feel right** — Manual inspection of top matches shows people who intuitively seem like they'd get along (qualitative gut-check).
2. **Conversations happen** — A meaningful percentage of seeded conversations go beyond the initial prompt exchange (at least 3+ back-and-forth messages).
3. **Content is the catalyst** — Users reference the shared content in their conversations rather than defaulting to generic small talk.

## Consequences

- **Speed to learning.** Cutting scope means faster launch, which means faster hypothesis validation. Every feature deferred is a feature that might never need to be built.
- **Small user base is leveraged, not worked around.** Full pairwise matching, heavier per-user processing, and opinionated match output all benefit from small scale.
- **Match quality ceiling is lower.** Without topic modeling, complementary interests, or behavioral refinement, some good matches will be missed and some mediocre ones will surface. This is acceptable — the MVP tests the direction, not the destination.
- **Interaction model is bare-bones.** A single seeded prompt per match may not be enough scaffolding for some users. If conversation rates are low, the first iteration should add more system-generated sparks (ADR-005 Layer 1) before adding user-generated content.
- **Clear upgrade path.** Every deferred feature (ADR-003 through ADR-005) is designed and documented. When the hypothesis is validated, the roadmap is already written.
