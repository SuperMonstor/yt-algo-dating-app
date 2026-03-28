# ADR-013: Video Tagging and Embedding Strategy

- **Date:** 2026-03-28
- **Status:** Accepted
- **Context:** Defines how videos are classified for user profiling and matching. Covers the tagging pipeline, cost analysis, quality comparisons, and the decision to move toward an embeddings-first approach with tags as the display layer.

## Decision

Use a **two-layer architecture**: embeddings as the matching engine (source of truth), LLM-generated tags as the display/explainability layer. Videos are embedded into vector space for similarity computation. Tags are generated per-cluster (not per-video) for human-readable match explanations.

## Context

### The problem we're solving

When a user uploads their YouTube Takeout, we need to understand *what* they watch — not just which channels, but which topics, at what depth, in what format. This understanding powers both the fingerprint ("here's what YouTube says about you") and matching ("here's why you two would get along").

### Approaches evaluated

We tested four approaches in sequence, each informing the next:

#### Approach 1: LLM tagging via Claude Code agents (original)

- **How:** Spawned Claude Code agents (Opus/Sonnet) to tag batches of 100 videos each
- **Prompt:** "Classify each video with 3-5 topics, domain, format, guest"
- **Results:** High quality — specific named entities ("bb ki vines angry masterji", "jannik sinner australian open"), deep domain hierarchies ("sports > tennis > australian open")
- **Cost:** ~$2-4 per 500 videos on Opus. Prohibitive at scale.
- **Speed:** 5-10 minutes per 400 videos

#### Approach 2: YouTube metadata (free, no LLM)

- **How:** Used YouTube API's `topicDetails` (Wikipedia categories), `categoryId`, and creator tags
- **Tested:** Fetched `topicDetails` for all 46K cached videos. 89% coverage.
- **Results:**
  - `topicDetails` is **too coarse and misleading**. "Lifestyle (sociology)" is applied to 32% sports content, cycling gear reviews, comedy sketches, and HealthyGamerGG psychology. Unusable for matching.
  - `categoryId` is only useful for **format detection** (Music=10, Gaming=20, Education=27). Too coarse for topics.
  - **Creator tags are specific but describe the channel, not the video.** HealthyGamerGG puts the same 5 tags ("mental health, drk, healthygamergg") on every video regardless of whether it's about AI therapy, introversion, or discipline. Chris Williamson tags everything "modern wisdom, podcast" — tells you nothing about Naval Ravikant's decision-making frameworks.
- **Cost:** Free
- **Verdict:** Useful as *input* to classification, not as classification output itself

#### Approach 3: Hybrid (free metadata + LLM fallback via Claude Max proxy)

- **How:**
  1. Skip music (`categoryId=10`), one-off channels, cached videos
  2. Videos with creator tags → extract topics from tags + infer domain from keywords (free)
  3. Videos without creator tags → LLM via Claude Max proxy at `localhost:3456` ($0)
- **Optimizations built:**
  - Tag cleaner: strips escaped slashes/quotes, filters spam ("subscribe", "official video", "hd"), deduplicates
  - Description cleaner: strips URLs, social handles, sponsor codes, "subscribe" CTAs. Reduces 414 avg chars → 149 chars (64% reduction)
  - Domain inference: keyword matching across title + channel + tags → hierarchical domain instead of raw categoryId
  - Batch size increased from 20 → 50 per LLM call
  - Claude Max proxy (`claude-max-api-proxy` npm package) routes through existing subscription
- **Results:** 76% tagged free, 24% via LLM. But free-tagged quality was poor — creator tags are channel-level, not video-level. Domain inference helps but can't match LLM understanding.
- **Cost:** $0 (proxy) or $0.03/user (Haiku API fallback)

#### Approach 4: All-LLM via proxy with improved prompt

- **How:** Tag everything through Haiku via Claude Max proxy, with a prompt optimized for specificity
- **Key prompt change:** Added explicit rules — "use proper nouns", "NEVER use generic tags", "include creator/show/person names", "think: would this tag help match two people who share this EXACT niche interest?"
- **Results:** Dramatic improvement over default Haiku. "tanmay bhat never have i ever" instead of "comedy challenge". "rush 2013 film, james hunt niki lauda" instead of "movie clip". Named entities, episode specifics, proper nouns.
- **Cost:** $0 via proxy
- **Batch size:** 15 videos per call (larger batches cause truncation with proxy)

### The embeddings insight

After all four approaches, a key insight emerged: **tags are the wrong primitive for matching.**

Problems with tag-based matching:
- Consistency — even with improved prompts, "artificial intelligence" vs "AI" vs "machine learning" still fragment
- Averaging — a simple tag frequency profile washes out niche interests when mainstream topics dominate
- Rigidity — discrete tags can't capture "almost the same interest" (marathon ≈ ultramarathon)

Embeddings solve all three:
- No consistency problem — similar concepts land near each other in vector space automatically
- Weighted representation — user profiles can be multi-centroid, preserving niche clusters
- Continuous similarity — "marathon training" and "ultramarathon" have high cosine similarity without needing to share a tag

## Architecture

### Layer 1: Embeddings (matching engine — source of truth)

```
Video → embed(title + channel + cleaned_description + creator_tags) → vector[384]
User  → weighted average of video embeddings → vector[384]
Match → cosine_similarity(user_A, user_B)
```

- Embedding model: `all-MiniLM-L6-v2` (free, local, 384 dimensions)
- User representation: NOT simple average. Use weighted cluster centroids to preserve niche signals.
- Matching: cosine similarity in vector space

### Layer 2: Dynamic clustering (niche discovery)

```
All video embeddings → HDBSCAN clustering → emergent niches
Each cluster = a naturally occurring interest area
```

Example clusters that emerge:
- "solo founder SaaS growth hacks"
- "deep house DJ transitions"
- "attachment styles in dating"
- "zone 2 running physiology"

No taxonomy needed. Niches emerge from the data.

### Layer 3: LLM labels (display layer — explainability)

```
For each cluster:
  Send 50 representative video titles to LLM
  Ask: "What's the theme? Give a specific, human-readable label."
```

Cost: ~2,000 LLM calls for 500K videos (one per cluster, not per video). ~$0.10 total.

Used for:
- Fingerprint display ("Your top interests: zone 2 running, stoic philosophy, indie horror games")
- Match explanations ("You both love Naval Ravikant's philosophy and niche cycling channels")
- Interest map visualization

### Where tags still live

LLM per-video tagging (Approach 4) is kept for:
- **Format detection** — podcast, interview, tutorial, documentary, music video, etc. Critical for the format-based signal weighting in ADR-010.
- **Guest identification** — "Andrew Huberman on Chris Williamson" enables "you both watched this specific episode" match seeds.
- **Fingerprint specificity** — users want to see specific topics, not cluster IDs.

### Processing pipeline for a new user

```
Upload takeout HTML
  → Parse & classify shorts vs long-form (existing)
  → Filter: skip music (categoryId=10), skip one-off channels
  → Check video cache (shared across all users)
  → Fetch missing metadata from YouTube API
  → Embed uncached videos (local model, free)
  → Tag uncached videos via LLM proxy (format + topics for display)
  → Store embeddings + tags in shared cache
  → Compute user profile (weighted cluster centroids)
  → Run matching (cosine similarity)
  → Label matched clusters (LLM, one-time per cluster)
  → Return fingerprint + matches
```

## Cost Analysis

### Per-video costs at scale

| Component | Cost per video | 500K videos |
|---|---|---|
| YouTube API metadata fetch | Free (10K quota/day) | $0 |
| Embedding (local model) | Free | $0 |
| Embedding (OpenAI API fallback) | $0.000002 | $0.08 |
| LLM tagging via proxy | Free (Max subscription) | $0 |
| LLM tagging via Haiku API | $0.00006 | $30 |
| LLM tagging via Haiku Batch API | $0.00003 | $15 |
| Cluster labeling (one-time) | ~$0.05/cluster | $100 (for 2K clusters) |

### Per-user costs (after cache is warm)

| Users processed | Cache hit rate | New videos/user | LLM cost/user (Haiku) | Embedding cost/user |
|---|---|---|---|---|
| 10 | ~10% | ~1,800 | $0.11 | $0.00 (local) |
| 100 | ~50% | ~1,000 | $0.06 | $0.00 |
| 1,000 | ~75% | ~500 | $0.03 | $0.00 |
| 10,000 | ~90% | ~200 | $0.01 | $0.00 |

### Filtering funnel (reduces what needs processing)

For a user with 25K raw entries:
```
25,000  raw watch history entries
  → 8,000   long-form (after shorts filter)
  → 5,000   unique videos (after dedup)
  → 4,400   non-music (after categoryId=10 filter)
  → 2,700   from channels watched 2+ times (after one-off filter)
  → varies  minus cache hits
```

## Description Cleaning

YouTube descriptions are 52% boilerplate. Before sending to LLM or embedding:

1. Strip lines containing URLs
2. Strip lines with social media handles (@username, instagram.com, etc.)
3. Strip "subscribe"/"follow me"/"like and share" lines
4. Strip sponsor/promo code lines
5. Strip lines under 5 characters
6. Stop at "Follow me on" / "Connect with me" sections
7. Cap at 150 characters

Result: 414 avg chars → 149 avg chars (64% reduction). Only meaningful content survives.

## Format-Based Signal Weighting

(Extends ADR-010)

Not all content formats carry equal matching signal:

- **Tier 1 — Full weight:** podcast, interview, tutorial, documentary, explainer, review, vlog, news, reaction. Deliberate content choices.
- **Tier 2 — Reduced weight (0.3×), niche only:** music video, live performance. Only channels under 50K subscribers. Preserves "you both found the same obscure artist" signal.
- **Tier 3 — Excluded:** clip, compilation, highlights, comedy sketch, other. Algorithmically-driven consumption.

## LLM Prompt V3 (optimized for Haiku specificity)

The prompt was iteratively refined through three rounds of A/B testing on 30+ videos each.

### Prompt evolution

**V1 (original):** "Be specific with topics." → Haiku produced generic tags ("comedy", "tv drama", "entertainment").

**V2 (improved):** Added "NEVER use generic tags", "use proper nouns", GOOD/BAD examples. → Much better ("tanmay bhat never have i ever" instead of "comedy challenge"). But format detection was still poor.

**V3 (current, enriched context):** Added YouTube categoryId, video duration, and channel description as input. Plus duration-based format hints in the prompt. → Format detection dramatically improved (trailers correctly tagged as "ad", 58-min videos as "tutorial", podcast clips as "interview").

### Key prompt rules that made the difference

1. **Explicit GOOD/BAD examples** — `"bb ki vines angry masterji" NOT "hindi comedy"`. Haiku needs concrete demonstrations.
2. **Generic word ban** — `NEVER use: comedy, entertainment, music, content, viral, trending, video, funny, interesting`. Forces Haiku to be specific.
3. **Duration → format mapping** — `<2min = clip/ad, 2-15min = most formats, 15-60min = documentary/tutorial, >60min = podcast/lecture`. Biggest single improvement for format detection.
4. **Matching framing** — `"Think: would TWO people sharing this exact tag be a meaningful signal?"` Changes Haiku's optimization target.
5. **Channel description as context** — Helps identify what kind of channel this is (e.g., "CNBC Make It" → business/entrepreneurship).

### Enriched input per video (V3)

```
[1] video_id: abc123
    title: How Discipline Changes Your Brain
    channel: Chris Williamson
    category: Education
    duration: 58min
    tags: modern wisdom, podcast, neuroscience
    description: Andrew Huberman explains the neuroscience of willpower
    channel_about: Chris Williamson hosts the Modern Wisdom podcast
```

Adding `category`, `duration`, and `channel_about` costs ~20 extra tokens per video but produces significantly better results from Haiku.

### Batch size

15 videos per LLM call (reduced from 50). Larger batches cause truncation with the proxy and reduce per-video attention from Haiku. At 15, Haiku reliably tags all videos in the batch with proper JSON output.

## Consequences

- **Embeddings are recomputable.** If we change models or parameters, re-embed everything. Tags are a cache, not source of truth.
- **Cache is the biggest cost lever.** Same video tagged/embedded once, reused across all users. At 10K users, 90%+ of videos are cache hits.
- **Claude Max proxy enables $0 LLM tagging** during the bootstrapping phase. Proxy routes through the existing subscription. Not suitable for production at scale — switch to Haiku API when user volume exceeds what the proxy can handle.
- **Multi-vector user profiles are critical.** Simple averaging washes out niche interests. User profiles should be represented as weighted cluster centroids, not a single vector.
- **Tags remain essential for UX.** Users don't understand "0.87 cosine similarity." They understand "You both watch Naval Ravikant's philosophy and niche cycling channels." The display layer matters as much as the matching engine.

## Options Considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Fixed taxonomy + rule-based | Free, consistent | Misses niche, rigid | Rejected — breaks the moment you go niche |
| YouTube metadata only | Free, 89% coverage | Too coarse ("Lifestyle" = everything), channel-level not video-level | Rejected as primary — useful as input |
| LLM per video (Opus agents) | Best quality | $2-4 per 500 videos | Too expensive at scale |
| LLM per video (Haiku + proxy) | Good quality with right prompt, $0 | Slower, needs prompt tuning | Good for bootstrapping |
| **Embeddings + cluster labeling** | Scales, captures niche, cheap | Needs local model setup | **Selected as production architecture** |

The embeddings approach is the best fit because it separates the hard problem (similarity computation) from the display problem (human-readable labels), solving each with the right tool.
