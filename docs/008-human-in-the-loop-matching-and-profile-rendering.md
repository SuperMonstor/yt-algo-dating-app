# ADR-008: Human-in-the-Loop Matching and Profile Rendering

- **Date:** 2026-03-26
- **Status:** Proposed

## Decision

Replace algorithmic matching in v1 with human-in-the-loop matching. The core technical problem shifts from computing similarity scores to rendering legible, glanceable user profiles that surface a person's genuine interests — enabling a human matchmaker to intuitively pair people. Manual matching decisions become training data for the eventual algorithm.

## Context

ADR-003 designed a full TF-IDF + cosine similarity matching engine. ADR-006 scoped it down for MVP. But the deeper realization is: before building an algorithm, we need to understand what makes a good match. A human who can see what two people are genuinely into can match intuitively — and every match they make (successful or not) teaches us what the algorithm should optimize for.

This also solves the cold-start problem differently. Instead of needing enough users for IDF weights to be meaningful, we need enough signal per user for a human to read their profile and say "I know who this person would click with."

## How It Works

### Profile as the Core Product

The primary technical output is a human-readable profile derived from YouTube consumption data. When a matchmaker looks at a profile, they should understand who this person is within 30 seconds.

### Interest Scoring: Depth x Specificity x Consistency

Each interest (channel or aggregated topic) is scored across three dimensions:

- **Depth** — total watch volume. More videos watched = stronger signal. One video is noise; 30 videos is real interest.
- **Specificity** — how niche the channel is, measured by inverse popularity (e.g., `1 / log(subscriber_count)`). Mr. Beast (300M subscribers) scores near zero. A WWII history channel with 50K subscribers scores high. This filters out mainstream content and "brain rot" that reveals nothing about the person.
- **Consistency** — how spread out the watches are over time. Measured by the number of distinct time periods (weeks or months) the interest appears in. 50 videos in one weekend = rabbit hole (low consistency). Videos every month for 18 months = core identity (high consistency).

The composite score:

```
interest_score = depth × specificity × consistency
```

This naturally surfaces interests that are niche, deep, AND sustained — the things that genuinely define a person. One-off binges, algorithmic recommendations, and mainstream scrolling all drop to the bottom.

### Profile Display

Interests are ranked by their composite score and presented to the matchmaker. The profile leads with what makes this person distinctive, not what makes them generic.

Possible profile elements (to be refined through use):

- **Top interests ranked by score** — clustered into 4-6 buckets with representative channels listed under each
- **Long-term vs. recent discovery** — interests with high consistency flagged as long-term; recent spikes flagged as new curiosity
- **LLM-generated summary** — a one-sentence "who is this person" based on their top interests (e.g., "Deep into Stoic philosophy and attachment theory, casual FPS gamer, watches productivity content late at night")
- **Raw top channels** — sometimes the channel list itself is the most honest view

### Matching Process

1. Parse Takeout data → extract channels, watch frequency, timestamps
2. Enrich channels → LLM semantic fingerprints + subscriber counts (per ADR-007)
3. Score interests → depth × specificity × consistency
4. Render profile → human-readable view of who this person is
5. Human matchmaker reviews profiles and pairs people
6. Track outcomes → which matches led to real conversations, which didn't

### From Manual to Algorithmic

Every manual match is a labeled data point: "this pair of profiles was matched by a human who thought they'd click." Combined with outcome data (did they actually talk?), this becomes a training set:

- **Positive signal:** matched + had a real conversation
- **Weak positive:** matched + exchanged a few messages
- **Negative signal:** matched + no engagement

Over time, this data reveals which profile similarities actually predict conversational compatibility — and that's what the algorithm should learn, rather than our assumptions about what should matter.

## Consequences

- **Matching quality starts high.** A human matchmaker with good profiles will outperform a cold-start algorithm. The tradeoff is it doesn't scale — but at launch scale, it doesn't need to.
- **The algorithm gets built on real data, not assumptions.** The TF-IDF weights, score formulas, and match thresholds from ADR-003 are educated guesses. Manual matching produces ground truth.
- **Profile rendering quality is critical.** If the profile doesn't surface the right information, the matchmaker can't do their job. This is now the highest-priority UX problem.
- **Consistency as a signal adds timestamp processing.** The Takeout parser needs to extract and bucket timestamps, not just count videos. This is straightforward but adds a step to the pipeline.
- **The "brain rot filter" is automatic.** Generic, mainstream content has low specificity. Binge-watched rabbit holes have low consistency. Neither surfaces on the profile without being manually filtered — the scoring handles it.
- **Clear transition path.** When the manual matching data is rich enough, the algorithm can be trained on what actually worked rather than theoretical similarity metrics. ADR-003's architecture (vectors, similarity, ANN search) still applies — but the weights and features are learned from real matches instead of guessed.
