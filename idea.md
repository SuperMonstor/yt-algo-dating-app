# YT Algo Dating App — Thesis

## The Core Insight

YouTube watch history is the most honest behavioral data that exists. Unlike Twitter (performative), Instagram (curated), or even Spotify (narrow), YouTube consumption is completely private and spans every dimension of a person's life — intellectual curiosity, humor, fitness, philosophy, music, cooking, learning style, politics, relaxation. Nobody watches a 3-hour podcast episode or a 20-minute video essay to signal anything to anyone. It's pure revealed preference — who you genuinely are when nobody's looking.

Two people with high YouTube overlap probably have a genuinely similar inner life in a way no other single platform can reveal.

## The Problem

Dating apps match on surface-level attributes — photos, bios, swiping behavior. They tell you nothing about how someone actually thinks, what they care about, or how they spend their private attention. The result is matches that look good on paper but have no depth. Conversations stall because there's no real common ground beyond mutual physical attraction.

## The Solution

A matching engine built on YouTube watch history. Not just "you both watch fitness content" — but "you both watch Jeff Nippard rather than Greg Doucette, which means you prefer evidence-based, calm delivery over entertainment-driven content." Not just "you both like philosophy" — but "you both watch continental philosophy rather than analytic, and you both found it through the same adjacent interest in psychology."

This granularity is what makes someone look at a match and feel genuinely understood rather than generically categorized.

## How It Works

### Data Ingestion

Users export their YouTube data via Google Takeout (takeout.google.com) and upload it to the app. This approach is deliberate:

- **No API dependency** — no OAuth complexity, no rate limits, no platform risk from Google changing terms
- **User trust** — people can see exactly what they're handing over; no ambient fear of "what else can this app access"
- **Quality filter** — the upload friction filters for genuinely invested users, ensuring a high-quality early user base

### The Content Fingerprint

The app maps each video in a user's watch history to its channel and broader topic categories, weighted by:

- **Recency** — what you watch now matters more than what you watched two years ago
- **Watch frequency** — subscribing to a channel but never watching it is very different from watching every upload
- **Completion rate** — starting a video vs. watching it through signals genuine interest
- **Depth patterns** — do you watch explainers and full lectures, or just clips and shorts?

This produces a multi-dimensional interest vector. The dimensions include:

- **Intellectual depth** — lectures and long-form vs. clips and highlights
- **Breadth of curiosity** — how many distinct interest areas you explore
- **Lifestyle signals** — fitness, cooking, travel, personal development
- **Personality proxies** — debate content vs. meditative content, confrontational comedy vs. wholesome comedy
- **Content archetype** — deep-diver vs. browser, specialist vs. generalist

The output is a "content fingerprint" — something like: *"You're 40% neuroscience & self-improvement, 25% startup & tech, 20% philosophy & psychology, 15% fitness. You're in the top 3% for philosophy consumption. Your watch pattern suggests you're a deep-diver rather than a browser."*

### The Matching Layer

Matching uses constellation similarity rather than simple overlap. The algorithm looks for:

- **Shared deep interests** — not just following the same channels, but engaging with the same depth
- **Adjacent curiosity patterns** — people who arrived at the same interests through similar paths
- **Complementary gaps** — where one person's strong interest overlaps with another's emerging curiosity
- **Taste alignment within categories** — the specific creators and styles within a topic reveal far more than the topic itself

Each match comes with a reason: *"You both deeply engage with these channels, you both consume these topics at similar depth"* — giving people a natural conversation starter that dating apps completely lack.

### Location

YouTube data doesn't reveal location. Users self-report their city at signup. The initial focus is Bangalore, which has a very active tech-intellectual scene and a dense concentration of the target demographic.

## Growth Strategy

### Phase 1 — The Fingerprint (Acquisition Engine)

The fingerprint is the free, viral hook. "Your intellectual DNA based on what you actually watch" is an extremely shareable concept. People are fascinated by self-knowledge. They'll screenshot their fingerprint and share it everywhere. That's the organic acquisition engine before matching even comes into play.

The product at this phase: upload your YouTube Takeout data, get a fascinating content fingerprint, and optionally opt into matching.

### Phase 2 — The Matching (Retention Engine)

Once there's a critical mass of users in a city, activate matching. Show people others with similar fingerprints, ranked by constellation similarity. Add in-app interaction — messaging, interest signaling, events for matched clusters.

### Phase 3 — Multi-Platform Enrichment (Defensibility)

Ingest additional platforms — Spotify, Substack, podcast apps, letterboxd — to build richer fingerprints. By this phase, the value is in the matching engine and community, not in any single platform's data. YouTube was the wedge; the proprietary interest graph is the moat.

## Key Design Principles

1. **Privacy-first** — Matching uses category-level signals, never specific video titles. Nobody needs to know someone watched a specific self-help video at 2am. The system just knows they're interested in personal development.

2. **Show the why** — Every match explains itself. "Here's why you were matched" is the single most important UX decision. It builds trust in the system and gives users a conversation starter.

3. **Honest signals only** — The entire premise rests on using private, unperformable behavior. Never introduce features that let people game or curate their profile. The watch history is the profile.

4. **Fingerprint as identity** — The content fingerprint should be compelling enough to be an identity artifact. People should want to share it, update it, compare it with friends. It's the atomic unit of the product.

5. **Friction as feature** — The Google Takeout upload process is friction, but it's also a trust signal and quality filter. Don't over-optimize it away. Guide users through it with care, but recognize that the people who complete it are exactly the users you want.

## Technical Leverage

YouTube's recommendation algorithm has already done half the clustering work. People who watch similar content get pushed into similar recommendation bubbles over time. Their watch histories naturally converge into clusters. This app is essentially building a matching engine on top of a clustering engine that Google has spent billions perfecting.

## The Thesis in One Line

**Match people based on who they actually are in private — as revealed by what they choose to watch when nobody's looking — not who they present themselves as in public.**
