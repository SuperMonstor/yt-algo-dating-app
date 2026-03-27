# ADR-009: Curated Introduction Engine Reframe

- **Date:** 2026-03-27
- **Status:** Accepted

## Decision

Reframe the product from a "dating app" to a **curated introduction engine for real-world communities**. The YouTube data predicts "these two people would have a good conversation" — not romantic compatibility. This is a more defensible, honest, and achievable value proposition.

## Context

Every dating app that promises compatibility gets blamed when relationships don't work out. By scoping the promise to solving the "who should I even meet" problem, we sidestep that trap entirely. The core thesis becomes: shared media consumption patterns are a strong signal for conversational chemistry, and that's a much easier problem to solve and a much easier promise to keep.

## Product Direction

### Profile as Interest Fingerprint

Users upload their takeout data and receive a distilled, shareable profile — not the raw data, but an interest fingerprint. Example: *"70% curiosity-driven, big into indie film and behavioral psychology, guilty pleasure is reality TV."* The profile communicates who you are without exposing what you watched.

### Constrained, Intentional Matching

Within a community (e.g., a run club), users receive **two or three introductions per week** with a short blurb explaining why they were matched. No infinite swipes. The constraint is the feature — it forces intentionality.

### Social Framing

The experience should feel like "your friend introducing you to someone," not "an algorithm picked you." The YouTube data is the engine, but it should be mostly invisible to the user after onboarding. Language and design should feel warm and human.

## Technical Approach

### Pipeline

1. Parse takeout JSON for watch history
2. Use an LLM to batch-categorize videos into interest clusters
3. Build a vector per person across those dimensions
4. Run similarity scoring within the community pool

At run-club scale (even a few hundred people), brute-force pairwise comparisons are sufficient — no fancy infrastructure needed.

### Matching Threshold

The key design decision is overlap calibration: surface matches with **strong overlap in at least two dimensions, but not identical across all of them**. Enough commonality for connection, enough difference for discovery.

## Launch Strategy

### Validate Before Building

Run a **one-time event** first rather than building a full app:

1. Collect takeout data from people in the run club
2. Process and generate matches
3. Host a mixer where people meet their matches in person

This tests the core thesis — do people matched this way actually have good conversations — without building real infrastructure. If conversations fall flat, we learn before writing a ton of code.

### Critical Friction Point

The make-or-break question: **will people actually go through the takeout export process?** A fallback to explore is a lighter-weight data collection path — such as connecting a YouTube account via OAuth to pull just subscriptions — if full takeout upload kills conversion.

## Consequences

- The product promise is scoped to introductions, not relationship outcomes — lower expectations, higher deliverability
- Community-first distribution (run clubs, interest groups) replaces cold-start user acquisition
- Event-based validation lets us test the thesis with near-zero engineering investment
- The "constrained introductions" model creates natural scarcity and intentionality
- Data collection friction remains the biggest risk to validate early
