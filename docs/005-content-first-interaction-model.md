# ADR-005: Content-First Interaction Model — Ideas Before People

- **Date:** 2026-03-24
- **Status:** Proposed

## Decision

Replace the standard "profile → cold message" dating app interaction model with a three-layer content-first system: system-generated sparks (zero effort), user-generated takes visible only to high-similarity matches (low effort), and emergent shared rabbit hole detection. Every interaction is anchored in ideas and shared interests, not in person-to-person cold outreach.

## Context

The "here's a profile, now send a message" model is where most dating app matches go to die. The blank chat screen offers no natural entry point for conversation. In contrast, social media generates natural interaction because content creates something to respond to — you react to an idea, not to a person.

However, the app's core thesis (ADR-003, idea.md) is built on private, unperformable behavior. Adding a content/posting system risks reintroducing performativity — people curating posts to seem interesting, which is exactly the Instagram/Twitter dynamic the app is designed to avoid.

The solution must thread this needle: create natural conversation entry points without incentivizing performance.

## How It Works

### Layer 1: System-Generated Sparks (Zero User Effort)

The system already knows what two matched users share (from ADR-003 vectors). It uses this to generate concrete conversation prompts:

- **Shared channel prompt**: "You and Priya both deeply follow [channel]. She recently watched [video title] — have you seen it?"
- **Interest-based question**: "Your top shared interest is continental philosophy. Here's a question: 'Is Heidegger's Dasein a useful lens for thinking about smartphones?'"
- **Temporal coincidence**: "You've both been going down a fermentation rabbit hole this month."
- **Complementary gap**: "You're deep into cognitive science. Arjun is just getting into it — he might appreciate your perspective."

Sparks are anchored in real shared interests, require no effort from either user, and give both people something concrete to talk about. The conversation starts with "oh yeah I loved that video" instead of "hey."

Spark generation can use an LLM to produce contextually interesting prompts from the shared interest data, or can be template-based for simplicity at launch.

### Layer 2: Takes — Interest-Anchored Micro-Posts (Low User Effort)

Users can post short "takes" — a thought, a hot take, a question, a reaction — tied to their interest areas. This is the most delicate layer because it's closest to social media posting. Critical design constraints:

**Prompted, not blank-slate.** The app suggests prompts based on the user's actual interests: "You've been watching a lot of [topic]. Got a take?" This makes it feel like reflective journaling rather than performing for an audience.

**Visible only to high-similarity matches.** A take is shown to ~15-30 people who share that interest area, not broadcast to the whole platform. This dramatically reduces performativity — you're sharing a thought with people who actually care about this topic, not optimizing for likes from strangers.

**Attached to an interest area.** Takes are tagged to specific interest domains from the user's fingerprint. This keeps content anchored to genuine interests and prevents drift into lifestyle flexing or generic dating-app posturing.

**No follower counts, no public metrics.** No visible like counts, no follower numbers, no virality mechanics. The only feedback is direct engagement — comments and DMs. This removes the gamification that drives performative behavior on social platforms.

Interaction patterns on takes:

- **React** — lightweight signal (find it interesting, agree, want to hear more). Visible only to the poster.
- **Comment** — starts a semi-public thread visible to other matches who share that interest. Small-group discussion, not a public forum.
- **DM about it** — "I saw your take on X, I actually think..." → private conversation with a built-in starting point. This is the primary conversion path from content to connection.

### Layer 3: Shared Rabbit Holes (Emergent, Zero Effort)

When the system detects that two matched users are both going deep on the same topic around the same time, it surfaces this explicitly:

"You and Arjun are both deep in [topic] right now."

Detection sources:
- Takeout re-uploads showing convergent recent consumption
- Both users posting takes in the same interest area
- Both users engaging with sparks in the same topic

This is the strongest natural conversation starter because it's timely and mutual. Neither person is reaching out cold — they're both in the same intellectual headspace right now. The system is just making the introduction that would happen naturally if they were in the same physical space.

### Interaction Hierarchy

The three layers create multiple on-ramps to conversation at different effort levels:

```
Passive (zero effort)     → Sparks: System surfaces shared interests
                               ↓
Reactive (minimal effort) → Takes: Respond to someone's idea
                               ↓
Active (low effort)       → Post: Share your own take
                               ↓
Emergent (zero effort)    → Rabbit Holes: System detects convergence
                               ↓
                          → Conversation: Ideas first, person second
```

Users who never post a single take can still have natural conversation starters via Sparks and Rabbit Holes. Takes are optional enrichment, not required participation.

### Feeding Back Into the Matching System (ADR-004)

Every interaction in this model produces behavioral signal:

- A take posted about topic X → confirms active interest in X
- A comment on someone's take → interest alignment signal
- A DM triggered by a take → strong match validation signal
- Engagement with a spark → confirms the shared interest is real, not just statistical

This data flows directly into the refinement loop from ADR-004, improving match quality without requiring Takeout re-uploads.

## Design Principle

**Every interaction is about ideas first, people second.** Users are drawn into conversation because they have something to say about a topic, not because they're trying to impress someone. The romantic or social connection emerges from intellectual resonance — which is the entire thesis of the app.

## Consequences

- **Lower conversation abandonment** — Matches come with built-in conversation starters, addressing the #1 failure mode of dating apps (matched but never talked).
- **Natural content moderation scope** — Takes are short, interest-anchored, and shown to small groups. This dramatically reduces the surface area for harassment, spam, or inappropriate content compared to open social platforms.
- **Performativity risk is reduced, not eliminated** — Despite the constraints, some users will inevitably try to perform. The small audience size, lack of metrics, and interest-anchoring make this less rewarding than on social platforms, but it can't be fully prevented. Monitor for drift.
- **Content generation is optional** — The system works even if most users never post. Sparks and Rabbit Holes are fully automated. This means low content-generation rates don't break the interaction model.
- **LLM dependency for Sparks** — High-quality system-generated prompts likely require an LLM, which adds cost and latency. Template-based fallbacks should exist for scale and reliability.
- **Adds product complexity** — This is significantly more complex than a simple matching + messaging app. The three-layer system needs careful UX to avoid overwhelming users. Launch with Layer 1 (Sparks) only, add Layer 2 (Takes) once validated, Layer 3 (Rabbit Holes) requires sufficient data and re-uploads.
