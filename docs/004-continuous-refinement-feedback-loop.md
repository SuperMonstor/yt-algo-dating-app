# ADR-004: Continuous Refinement — Evolving Matches Beyond the Initial Upload

- **Date:** 2026-03-24
- **Status:** Deferred

## Decision

Treat YouTube Takeout data as the cold-start signal and layer in three ongoing refinement mechanisms: implicit behavioral feedback from in-app interactions, periodic Takeout re-upload nudges, and temporal decay on historical data. Over time, the matching system transitions from YouTube-derived vectors to a hybrid of YouTube + behavioral signals.

## Context

Google Takeout is a snapshot, not a stream. Users upload once and get initial matches, but interests evolve and the matching model needs to learn what "good match" actually means for each user. Without a refinement mechanism, matches degrade over time as the underlying data grows stale and the model can't learn from its own successes and failures.

## How It Works

### Implicit Behavioral Feedback

Once users are on the platform, every interaction produces signal:

| Signal | Interpretation | Vector Impact |
|---|---|---|
| Opens a match profile | Mild interest in that match's interest areas | Slight upweight of overlapping interests |
| Messages a match | Strong interest | Upweight shared interests, validate match |
| Long conversation (many exchanges) | Strong match validation | High-confidence positive training signal |
| Ignores a match for days | Weak or negative signal | Slight downweight or no change |
| Hides or blocks a match | Strong negative signal | Downweight differentiating interests of that match |
| Engages with a post in topic X | Active/growing interest in X | Upweight topic X in user vector |
| Posts a take about topic Y | Y is a currently active interest | Upweight topic Y, mark as high-confidence current interest |

These signals serve two purposes:

1. **Individual vector refinement** — Update the user's interest vector based on what they're actively engaging with on the platform. Interests they pursue in-app get upweighted; interests they show no engagement around gradually fade.

2. **Global model training** — Aggregate outcomes across all matches to learn what similarity dimensions actually predict good interactions. If high channel-level similarity consistently produces better conversations than high topic-level similarity, the hybrid score weights from ADR-003 (0.6/0.25/0.15) should shift accordingly. This can be done periodically via batch analysis or continuously via online learning.

### Periodic Re-Upload Nudges

Every 3-6 months, prompt users to re-upload their Takeout data. This is the only mechanism for getting fresh YouTube consumption data.

Frame re-uploads as self-discovery rather than maintenance: "Your fingerprint is 4 months old. Want to see how you've changed?" Show a diff of their old fingerprint vs. new one — this is intrinsically interesting and motivates the upload.

The re-upload cadence can be adaptive: if the system detects significant drift between a user's in-app behavior and their YouTube-derived profile (they're engaging with matches in areas their YouTube data doesn't reflect), nudge earlier.

### Temporal Decay

Apply exponential decay to YouTube consumption data based on timestamps. Watching a channel heavily 2 years ago should count for much less than watching it last month. The Takeout data includes timestamps, so decay weights are computed at upload time.

As time passes since the last upload, decay continues to devalue all signals in the original data. This is honest — the system's confidence in the user's profile naturally diminishes, which:

- Triggers re-upload nudges ("Your profile confidence is getting low")
- Shifts matching weight toward in-app behavioral signals, which are always current
- Prevents stale data from dominating fresh behavioral evidence

### The Refinement Lifecycle

```
YouTube Takeout (cold start)
  → Initial TF-IDF vectors + matches (ADR-003)
    → User interacts on platform
      → Behavioral signals refine individual vectors
        → Better, more personalized matches
          → More meaningful interactions
            → More signal, better global model
              → Periodic re-upload refreshes base data
                → Cycle continues
```

### What the System Learns Over Time

- **Per-user**: Which interest dimensions matter most to this specific person for compatibility. Some users care deeply about intellectual depth alignment; others care more about lifestyle overlap. The system learns this from their engagement patterns.
- **Per-cohort**: Which types of similarity predict successful interactions for different user segments. Users in the "deep philosophy + tech" cluster might need different matching criteria than users in the "fitness + personal development" cluster.
- **Globally**: The optimal weights for the hybrid matching score, the right thresholds for "deep interest," and which constellation signals (shared deep interests vs. adjacent curiosity vs. complementary gaps) are most predictive.

## Consequences

- **Matches improve over time** — The system gets better for each user the longer they're on the platform, creating a natural retention loop.
- **Reduced dependence on Takeout over time** — As behavioral data accumulates, the system becomes less reliant on YouTube data, which de-risks the Google Takeout dependency.
- **Cold start remains the weakest point** — New users with no in-app behavior are matched purely on YouTube data. The quality gap between new and established users could create a two-tier experience. Mitigate by ensuring the cold-start matching (ADR-003) is strong enough to produce good initial interactions.
- **Feedback loops can amplify bias** — If the system learns that users engage more with matches who share interest X, it will show more X-heavy matches, which generates more X engagement signal, creating a filter bubble. Periodically inject diversity into match suggestions to counteract this.
- **Privacy implications of behavioral tracking** — In-app behavior tracking must be transparent to users. The app should be clear about what signals it collects and how they refine matching. This is consistent with the privacy-first principle but needs explicit UX treatment.
