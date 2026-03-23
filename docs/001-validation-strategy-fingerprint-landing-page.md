# ADR-001: Validation Strategy — Fingerprint Landing Page

**Date:** 2026-03-23
**Status:** Accepted
**Context:** Pre-build validation of the core product thesis

## Decision

Validate the YT Algo Dating App concept by launching a landing page where users can upload their Google Takeout YouTube data and receive a shareable "content fingerprint" — before any matching functionality exists. The dating app is framed as "coming soon" while the fingerprint serves as both the validation mechanism and the viral acquisition engine.

## Context

We need to answer two questions before investing in the full matching engine:

1. **Will people actually upload their YouTube data?** The Google Takeout flow has real friction — the export can take hours, the file is large, and people are protective of their watch history. If users won't clear that hurdle, the entire product premise falls apart.
2. **Is the fingerprint compelling enough to share?** The growth thesis depends on people screenshotting their fingerprint and posting it on social media. If the output isn't interesting or surprising enough, the viral loop won't ignite.

A landing page with fingerprint generation answers both questions with minimal build cost.

## How It Works

### User Flow

1. User lands on the page — sees the pitch: "Discover your intellectual DNA based on what you actually watch. A new kind of dating app is coming — one that matches you on who you really are."
2. User is guided through exporting their YouTube data via Google Takeout (step-by-step walkthrough, possibly with screenshots or a short screen recording).
3. User uploads the Takeout file.
4. The app parses the watch history and generates a content fingerprint:
   - **Interest breakdown** — percentage distribution across categories (e.g., "40% neuroscience & self-improvement, 25% startup & tech, 20% philosophy, 15% fitness")
   - **Consumption archetype** — deep-diver vs. browser, specialist vs. generalist, binge-watcher vs. daily grazer
   - **Standout stats** — "You're in the top X% for philosophy content," "You've watched 200+ hours of long-form interviews"
   - **Taste signatures** — the specific creators and content styles that define their profile within each category
5. The fingerprint is presented in a visually compelling, screenshot-friendly format.
6. User is prompted to share their fingerprint and sign up for the waitlist (email + city).

### What We Collect at Signup

- Email address
- City (self-reported) — essential for future location-based matching
- Consent to store their processed fingerprint data (category-level signals only, not raw watch history)

### What We Explicitly Don't Do

- Store raw watch history or specific video titles — the fingerprint is computed on upload and only category-level aggregates are persisted
- Promise a matching timeline — "coming soon" is deliberately vague
- Build any matching functionality — this phase is purely about validation and data collection

## What This Validates

| Signal | What it tells us |
|--------|-----------------|
| Upload completion rate | Whether users will tolerate the Google Takeout friction |
| Time-on-page after fingerprint | Whether the output is genuinely interesting |
| Share rate | Whether the fingerprint is compelling enough for organic virality |
| Waitlist signups | Whether people actually want matching based on this data |
| City distribution | Where to launch matching first (hypothesis: Bangalore) |
| Qualitative feedback | What parts of the fingerprint surprise or resonate most |

## Success Criteria

- **Minimum:** 100 completed uploads in the first month with >30% waitlist conversion
- **Strong signal:** Organic shares drive >20% of new visitors (trackable via referral params or share links)
- **Kill signal:** <50 uploads after targeted promotion, or fingerprint share rate <5%

## Why This Approach

**Fingerprint-first, not matching-first.** Building matching requires a critical mass of users in the same city. But the fingerprint is valuable to an individual — it's a self-knowledge tool. This means the product delivers value from user #1, with zero network effects required. The matching layer comes later once density exists.

**The fingerprint is the viral primitive.** People love seeing themselves reflected back through their data (Spotify Wrapped proved this at scale). A YouTube equivalent — covering a much broader slice of someone's identity — should be even more compelling. Each share is a free ad that speaks directly to the kind of person who would use the product.

**Friction filters for quality.** The Google Takeout process is annoying, but the people who complete it are exactly the high-intent, intellectually curious users the app needs. This is a feature, not a bug — it self-selects the target demographic.

## Consequences

- We'll have real data on whether the core thesis holds before building the expensive parts (matching engine, messaging, profiles)
- Early users form the seed of the waitlist and provide the initial data for matching when it launches
- The fingerprint format and categories will need iteration based on what users actually find interesting vs. generic
- If the viral loop works, we may face scale challenges with Takeout file processing before the matching product is ready
- We're collecting city data early, which lets us identify the best launch city empirically rather than guessing
