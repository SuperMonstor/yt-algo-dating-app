# ADR-002: MVP — Landing Page with YouTube Fingerprint

**Date:** 2026-03-23
**Status:** Proposed

## Decision

Build the MVP as a single landing page where users upload their Google Takeout YouTube data and receive a shareable "content fingerprint" with personalized insights. Users are automatically added to the waitlist for the dating app. The visual design follows the Moment Search landing page aesthetic (documented in `docs/style-guide.md`).

## Context

Before building matching, we need to validate two things: (1) will users upload their YouTube data, and (2) is the fingerprint output compelling enough to share? The MVP is scoped to answer both with minimal build cost.

The landing page has two jobs:
1. **Acquisition** — the fingerprint is interesting enough that people share it, driving organic traffic
2. **Waitlist building** — every user who uploads data is opted into the waitlist with their city, seeding the eventual matching pool

## How It Works

### Page Structure

**Above the fold:**
- Hero with the value prop: discover your intellectual DNA based on what you actually watch
- Clear CTA to get started
- Frame the dating app as "coming soon" — this is the teaser

**Upload flow:**
- Step-by-step guide to Google Takeout export (make this as frictionless as possible — screenshots, timing expectations, what to select)
- File upload area
- Processing indicator while the data is analyzed

**Fingerprint output:**
- Interest breakdown — percentage distribution across categories
- Consumption archetype — deep-diver vs. browser, specialist vs. generalist, binge-watcher vs. daily grazer
- Standout stats — "top X% for philosophy content," "200+ hours of long-form interviews"
- Taste signatures — specific creators and styles that define their profile
- Designed to be screenshot-friendly and shareable

**Waitlist capture:**
- Email + city (required to see full results, or gated after a preview)
- Automatic waitlist enrollment — no separate "join waitlist" step

### Key UX Decisions to Resolve

1. **Onboarding friction** — Google Takeout can take hours to prepare. Do we:
   - Have users start the export and come back later?
   - Send an email when their export is ready to upload?
   - Explore if there's a faster path (e.g., only exporting YouTube history, not the full Takeout)?

2. **Gating strategy** — When do we collect email/city?
   - Before upload (risk: drop-off before they see value)
   - After fingerprint preview (show a teaser, gate the full results behind signup)
   - After full results (risk: they screenshot and leave without signing up)

3. **Shareability format** — What makes the best shareable artifact?
   - A static image card (like Spotify Wrapped)
   - A unique URL with their fingerprint page
   - Both

4. **Privacy messaging** — How explicitly do we communicate what we do/don't store?
   - The fingerprint is computed from the upload; raw history is not stored
   - Only category-level aggregates are persisted
   - This needs to be front and center given the sensitivity of watch history

### Fingerprint Analysis Engine

The core analysis that needs to be built:

**Input:** Google Takeout YouTube watch history (JSON/HTML)

**Processing:**
- Parse watch history entries (video title, channel, timestamp)
- Categorize each video/channel into interest categories
- Weight by recency, frequency, and engagement patterns
- Compute the multi-dimensional interest vector

**Output:**
- Category distribution (percentages)
- Archetype classification
- Standout metrics
- Creator/taste signatures

### What We Learn

| Metric | What it tells us |
|--------|-----------------|
| Landing page → upload start rate | Is the pitch compelling? |
| Upload start → upload complete rate | Is the Takeout friction tolerable? |
| Upload → share rate | Is the fingerprint output interesting? |
| Share → new visitor rate | Does the viral loop work? |
| Overall waitlist signups + city data | Where to launch matching first |

## Consequences

- We ship a usable product quickly with a single page and a data processing pipeline
- The fingerprint engine built here becomes the foundation of the matching algorithm later
- Early data on category distributions and user interests informs how to build the matching layer
- If shareability is high, we may need to scale file processing infrastructure before matching is ready
- The Takeout friction remains the biggest risk — the onboarding guide quality will make or break conversion
