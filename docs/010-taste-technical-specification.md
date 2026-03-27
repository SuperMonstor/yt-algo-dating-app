# ADR-010: Taste — Technical Specification

- **Date:** 2026-03-27
- **Status:** Proposed

## Decision

Define the full technical specification for Phase 1 of Taste: a web app that turns YouTube watch history into a shareable "taste fingerprint" — a visual portrait of who you are based on what you actually watch.

## Context

ADR-009 reframed the product as a curated introduction engine. This spec translates that vision into a buildable system. Phase 1 focuses exclusively on the fingerprint generation and sharing flow — the viral loop that grows the user pool before matching (Phase 2) launches. The fingerprint itself IS the product for now: it turns the data collection step (normally pure friction) into the value moment.

## Product Overview

Taste is a web app that turns YouTube watch history into a shareable "taste fingerprint" — a visual portrait of who you are based on what you actually watch. The immediate product is the fingerprint itself (designed to go viral as a shareable card). The long-term product is a curated introduction engine for real-world communities, starting with a run club in Bengaluru.

### Core Thesis

YouTube watch history is one of the most honest signals of who someone actually is. People curate their dating profiles but not their 2am rabbit holes. By processing this data, we can generate a rich identity portrait and eventually match people who would have great conversations.

### MVP Scope

Phase 1 (build now): Upload takeout data → get your fingerprint → share it → join the waitlist.
Phase 2 (build after validation): Match people within communities → weekly intros → conversation UI.

This spec covers Phase 1 only.

## User Flow

1. User lands on the homepage (clean, minimal — one CTA: "Discover your taste fingerprint")
2. User sees brief instructions on how to export YouTube data from Google Takeout
3. User uploads their `watch-history.json` file
4. Server processes the file (show a loading state with personality — "Reading your 2am rabbit holes...")
5. User sees their fingerprint result page:
   - **Primary identity**: a narrative sentence summarizing their top 2-3 dimensions ("You're a curious builder — equal parts startup grindset, behavioral science, and indie film")
   - **Taste dimensions**: a visual breakdown of their interest weights (not raw percentages — styled as a distinctive graphic)
   - **Signature interests**: their niche hooks — the rare, specific channels/topics that make them unique
   - **Guilty pleasure / surprise**: the thing in their history that breaks the pattern
6. User can share a generated card (optimized for Instagram stories and Twitter/X) with a "get yours" link
7. User optionally joins the waitlist for community matching

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Deployment**: Vercel
- **Database**: Supabase (single `profiles` table for now)
- **Styling**: Tailwind CSS
- **LLM**: Claude API (Sonnet) for video classification and fingerprint narrative generation
- **Enrichment**: YouTube Data API v3
- **OG images / share cards**: @vercel/og or Satori for dynamic image generation

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Upload UI  │────>│  API Route   │────>│  YouTube Data   │
│  (client)   │     │  /api/process│     │  API (enrich)   │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Claude API  │
                    │  (classify   │
                    │   + narrate) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌─────────────────┐
                    │  Fingerprint │────>│   Supabase      │
                    │  Engine      │     │   (store)       │
                    └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Result Page │
                    │  + Share Card│
                    └──────────────┘
```

## Database Schema (Supabase)

### Table: `profiles`

| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | Auto-generated |
| created_at | timestamptz | Auto-generated |
| name | text | User's display name |
| email | text (nullable) | For waitlist, optional |
| fingerprint_vector | jsonb | Weighted dimension scores, e.g. `{"indie_film": 0.72, "behavioral_psych": 0.65, ...}` |
| hooks | jsonb | Array of niche interest objects, e.g. `[{"label": "Japanese city pop", "rarity": 0.03, "channels": ["Plastic Love Records"]}]` |
| primary_identity | text | Generated narrative sentence |
| guilty_pleasure | text | The pattern-breaking interest |
| dimension_labels | jsonb | Ordered list of top dimensions with human-readable labels |
| share_slug | text (unique) | Short unique slug for the share URL |
| video_count | integer | Total videos processed |
| top_channels | jsonb | Top 10 channels by weighted watch count |
| raw_stats | jsonb | Processing metadata: total videos, date range, enrichment coverage |

### Table: `video_cache`

| Column | Type | Description |
|--------|------|-------------|
| video_id | text (PK) | YouTube video ID |
| title | text | Video title |
| channel_name | text | Channel name |
| channel_id | text | YouTube channel ID |
| yt_category | text | YouTube's own category |
| tags | jsonb | Tags from YouTube API |
| description_snippet | text | First 200 chars of description |
| classified_dimensions | jsonb | LLM-generated dimension tags with weights, e.g. `{"urban_design": 0.8, "japanese_culture": 0.5}` |
| classified_at | timestamptz | When the LLM classification was done |

### Table: `dimension_taxonomy`

| Column | Type | Description |
|--------|------|-------------|
| id | text (PK) | Slug, e.g. `behavioral_psych` |
| label | text | Human-readable, e.g. "Behavioral psychology" |
| cluster_keywords | jsonb | Array of related terms that map to this dimension |
| video_count | integer | How many videos in the cache map to this dimension |
| user_count | integer | How many users have this in their top 10 |

This table is populated through the emergent taxonomy process (see Fingerprinting Pipeline below) and is updated periodically as the video cache grows. It is NOT pre-seeded with a fixed list.

## Fingerprinting Pipeline

This is the core algorithm. It runs server-side when a user uploads their data.

### Step 1: Parse and Deduplicate

```
Input: watch-history.json from Google Takeout
Output: Array of { videoId, title, channel, timestamp }
```

- Parse the JSON (it's an array of watch events)
- Extract video ID from the `titleUrl` field (format: `https://www.youtube.com/watch?v=VIDEO_ID`)
- Some entries may be "Watched a video that has been removed" — skip these
- Some entries may be ads or YouTube Music plays — filter by URL pattern
- Deduplicate but COUNT duplicates (rewatches are a signal)
- Record: `{ videoId, title, channelName, watchCount, timestamps[] }`

### Step 2: Enrich via YouTube Data API

```
Input: Array of unique video IDs
Output: Enriched video objects with metadata
```

- Check `video_cache` table first — skip any video already cached
- Batch uncached videos into groups of 50 (API limit per request)
- Call YouTube Data API `videos.list` with `part=snippet` for each batch
- Extract: category, tags, channel ID, description snippet
- Store results in `video_cache`
- Handle quota limits gracefully (YouTube API has a daily quota of ~10,000 units; each videos.list call costs 1 unit, so 200 calls = 10,000 videos is fine for a single user)

### Step 3: Classify via LLM (Emergent Taxonomy)

```
Input: Enriched video objects not yet classified
Output: Dimension tags with weights per video
```

This is the key design decision: we do NOT use a predefined category list. Instead:

**For each unclassified video, send to Claude Sonnet:**

```
System: You are a content classifier. Given a YouTube video's title, channel name,
category, and tags, output 2-5 topic tags that describe what this video is about.
Be specific — prefer "behavioral psychology" over "science", prefer "Japanese
urbanism" over "travel". Each tag should be a lowercase phrase, 1-3 words.

Respond in JSON: { "tags": [{"tag": "behavioral psychology", "weight": 0.8}, ...] }
Weights should sum to approximately 1.0.
```

**Batch this efficiently:** Send 20-30 videos per LLM call by putting them in a numbered list and asking for a JSON array of responses. This cuts API calls dramatically.

**Clustering pass (run periodically, not per-upload):**
- Collect all unique tags generated across the video cache
- Use an LLM to cluster semantically similar tags: "city planning", "urban design", "urbanism" → cluster under "urban design"
- Store the canonical cluster mapping in `dimension_taxonomy`
- Map all video tags to their canonical dimension

**For a new user upload:** most of their videos will already be in the cache with classifications. Only truly new videos need LLM classification. The clustering pass runs after every ~500 new videos added to the cache, or can be triggered manually.

### Step 4: Build Engagement-Weighted Profile

```
Input: User's watch list with counts + classified videos
Output: Weighted dimension vector
```

For each video the user watched, compute an engagement weight:

```javascript
function engagementWeight(video, userWatchData) {
  let weight = 1.0;

  // Rewatch bonus: watching something twice is a strong signal
  if (userWatchData.watchCount >= 2) weight *= 1.5;
  if (userWatchData.watchCount >= 4) weight *= 2.0;

  // Channel depth: watching many videos from one channel = genuine interest
  const channelVideoCount = userWatchData.channelCounts[video.channelId];
  if (channelVideoCount >= 5) weight *= 1.3;
  if (channelVideoCount >= 15) weight *= 1.6;

  // Late night bonus: watching at 11pm-4am suggests active choice, not passive
  const hour = new Date(userWatchData.timestamps[0]).getHours();
  if (hour >= 23 || hour <= 4) weight *= 1.2;

  // Recency bonus: recent watches reflect current identity more than old ones
  const daysSinceWatch = (Date.now() - new Date(userWatchData.timestamps[0])) / (1000 * 60 * 60 * 24);
  if (daysSinceWatch < 90) weight *= 1.2;

  return weight;
}
```

Then aggregate across all videos:

```javascript
// For each dimension, sum up (video's weight in that dimension * engagement weight)
const dimensionScores = {};
for (const video of userVideos) {
  const ew = engagementWeight(video, watchData[video.id]);
  for (const { dimension, weight } of video.classifiedDimensions) {
    dimensionScores[dimension] = (dimensionScores[dimension] || 0) + (weight * ew);
  }
}

// Normalize to 0-1 range
const maxScore = Math.max(...Object.values(dimensionScores));
for (const dim in dimensionScores) {
  dimensionScores[dim] /= maxScore;
}
```

### Step 5: Extract Hooks (Niche Interests)

```
Input: User's dimension scores + community-wide frequency data
Output: Array of hook objects
```

Hooks are interests that are both strong for this user AND rare in the user pool.

```javascript
function extractHooks(userScores, communityFrequency, userChannels) {
  const hooks = [];

  // Dimension-level hooks: dimensions where user scores high but few others do
  for (const [dim, score] of Object.entries(userScores)) {
    if (score < 0.3) continue;
    const frequency = communityFrequency[dim] || 0;
    const hookScore = score * (1 - frequency);
    if (hookScore > 0.4) {
      hooks.push({ type: 'dimension', label: dim, score, rarity: 1 - frequency });
    }
  }

  // Channel-level hooks: specific channels the user watches a lot that are rare
  for (const [channelId, count] of Object.entries(userChannels)) {
    if (count < 3) continue;
    const communityWatchers = getCommunityChannelCount(channelId);
    if (communityWatchers <= 3) {
      hooks.push({
        type: 'channel',
        label: getChannelName(channelId),
        watchCount: count,
        rarity: 1 - (communityWatchers / totalUsers)
      });
    }
  }

  return hooks.sort((a, b) => b.rarity - a.rarity).slice(0, 10);
}
```

### Step 6: Generate the Fingerprint Narrative

```
Input: Dimension scores, hooks, top channels, guilty pleasure
Output: Human-readable fingerprint text
```

Send to Claude Sonnet:

```
System: You generate short, punchy personality descriptions based on someone's
YouTube watching patterns. Be warm, specific, and a little playful. Never generic.
Write like a friend who knows them well, not like a personality quiz.

User: Here is someone's taste profile:
- Top dimensions: {top 5 dimensions with scores}
- Signature interests (rare for this community): {hooks}
- Top channels: {top 10 channels}
- Most-rewatched content: {top rewatched videos}
- Their most pattern-breaking interest: {dimension that least correlates with the rest}

Generate:
1. primary_identity: A 1-2 sentence narrative summary
2. guilty_pleasure: A playful 1-sentence callout of their pattern-breaking interest
3. dimension_labels: For their top 6 dimensions, generate a short human-readable label

Respond in JSON.
```

## API Routes

### `POST /api/process`

Main processing endpoint. Accepts the takeout JSON file.

**Request:** multipart/form-data with `file` (the watch-history.json) and `name` (display name)

**Response:**
```json
{
  "profileId": "uuid",
  "shareSlug": "abc123",
  "fingerprint": {
    "primaryIdentity": "You're a curious builder...",
    "dimensions": [
      { "id": "behavioral_psych", "label": "Behavioral psychology", "score": 0.82 },
      { "id": "startups", "label": "Startup culture", "score": 0.71 }
    ],
    "hooks": [
      { "label": "Japanese city pop", "rarity": 0.97 }
    ],
    "guiltyPleasure": "For someone so into deep tech, you sure watch a lot of reality TV",
    "topChannels": ["Veritasium", "Y Combinator"],
    "videoCount": 4832,
    "dateRange": { "from": "2019-03-15", "to": "2025-12-28" }
  }
}
```

**Processing steps (in order):**
1. Parse and validate the JSON file
2. Extract and deduplicate video entries
3. Check video_cache for already-enriched videos
4. Enrich uncached videos via YouTube Data API
5. Classify unclassified videos via Claude API
6. Compute engagement-weighted dimension scores
7. Extract hooks
8. Generate narrative via Claude API
9. Store profile in Supabase
10. Return fingerprint

**Expected processing time:** 15-45 seconds depending on cache hit rate. Use streaming or polling for the loading state.

### `GET /api/profile/[slug]`

Returns a public profile by share slug. Used for the share page and OG image generation.

### `GET /api/og/[slug]`

Generates the OG image / share card for a profile. Returns a PNG optimized for social sharing (1200x630 for Twitter/link previews, 1080x1920 for Instagram stories).

### `POST /api/waitlist`

Adds an email to the waitlist. Fields: email, profileId (optional, links to their fingerprint).

## Pages

### `/` — Homepage
- Hero: "Discover your taste fingerprint"
- Brief explanation of what it does (2-3 lines max)
- CTA button → goes to `/upload`
- Social proof: counter of fingerprints generated (pull from Supabase count)

### `/upload` — Upload Flow
- Step 1: Instructions on how to get YouTube Takeout data (with screenshots/visual guide)
- Step 2: File upload dropzone + name input
- Step 3: Processing state with personality (animated, fun loading messages)

### `/fingerprint/[slug]` — Result Page
- The full fingerprint display
- Share button that generates the card
- "Join the waitlist" CTA below the fingerprint
- If viewing someone else's fingerprint: "Get yours" CTA

### `/waitlist` — Simple Waitlist Signup
- Email input
- "We'll notify you when matching goes live in your community"

## Share Card Design

The generated image should include:
- User's name
- Primary identity sentence
- Top 5 dimensions as a visual (horizontal bars, radar chart, or custom graphic — NOT a pie chart)
- 2-3 signature hooks as pills/tags
- "taste.app" branding + "get yours" URL
- Clean, minimal, dark or light variant

Two formats:
- **Link preview (1200x630)**: for Twitter/X, iMessage, WhatsApp link unfurls
- **Story card (1080x1920)**: for Instagram stories, with more vertical space for detail

## Environment Variables

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
YOUTUBE_DATA_API_KEY=
ANTHROPIC_API_KEY=
```

## File Structure

```
taste/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                    # Homepage
│   ├── upload/
│   │   └── page.tsx                # Upload flow
│   ├── fingerprint/
│   │   └── [slug]/
│   │       └── page.tsx            # Result page
│   ├── waitlist/
│   │   └── page.tsx                # Waitlist signup
│   └── api/
│       ├── process/
│       │   └── route.ts            # Main processing endpoint
│       ├── profile/
│       │   └── [slug]/
│       │       └── route.ts        # Public profile data
│       ├── og/
│       │   └── [slug]/
│       │       └── route.ts        # OG image generation
│       └── waitlist/
│           └── route.ts            # Waitlist signup
├── lib/
│   ├── supabase.ts                 # Supabase client
│   ├── youtube.ts                  # YouTube Data API helper
│   ├── classifier.ts               # LLM classification logic
│   ├── fingerprint.ts              # Core fingerprinting engine
│   │   ├── parse.ts                # Takeout JSON parsing
│   │   ├── enrich.ts               # YouTube API enrichment
│   │   ├── classify.ts             # LLM batch classification
│   │   ├── weight.ts               # Engagement weighting
│   │   ├── hooks.ts                # Hook extraction
│   │   └── narrate.ts              # Narrative generation
│   └── share.ts                    # Share card generation
├── components/
│   ├── UploadDropzone.tsx
│   ├── ProcessingState.tsx
│   ├── FingerprintDisplay.tsx
│   ├── DimensionChart.tsx
│   ├── HookPills.tsx
│   ├── ShareButton.tsx
│   └── WaitlistForm.tsx
├── public/
│   └── ...
├── .env.local
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## Key Design Decisions and Rationale

### Why Emergent Taxonomy Over Predefined Categories
A fixed category list forces compromises. A video about "how Tokyo's train system reflects Japanese work culture" doesn't fit "travel" or "urban design" or "culture" — it's all three. By letting the LLM generate open-ended tags and then clustering them, the taxonomy reflects what people actually watch, not what we assumed they'd watch. The taxonomy also evolves as the user pool grows.

### Why Engagement Weighting Matters
Raw video counts treat autoplay the same as intentional deep-dives. The engagement heuristics (rewatch count, channel depth, time of day, recency) add resolution. Someone who watched 30 videos from one channel at 2am over the last month has a fundamentally different relationship with that content than someone who let one video autoplay during lunch six months ago.

### Why Hooks Are Scored by Inverse Frequency
Broad interests like "fitness" are useless for matching — everyone in a run club watches fitness content. The value is in specific, rare overlaps. Inverse frequency weighting surfaces the "you both watch this obscure channel" moments that make introductions feel serendipitous rather than algorithmic.

### Why Limited Matches Per Week (Phase 2)
Constraint creates intentionality. Infinite swipes → paradox of choice → nobody messages. Three intros per week → each one feels curated → higher engagement per match.

### Why the Fingerprint Itself Is the Viral Product
The upload-and-share flow turns the data collection step (normally pure friction) into the value moment. People share personality-reveal content compulsively. Every share includes a "get yours" link, creating a viral loop that grows the match pool before matching even launches.

## Performance and Cost Considerations

### YouTube Data API
- Quota: ~10,000 units/day on the free tier
- Each `videos.list` call = 1 unit, returns up to 50 videos
- A user with 5,000 videos = 100 API calls = 100 units
- With caching, most popular videos are only fetched once across all users
- At scale, apply for higher quota or use the video_cache to minimize calls

### Claude API (Classification)
- Batch 20-30 videos per call to minimize requests
- A user with 5,000 videos where 2,000 are uncached = ~80 LLM calls
- Use Claude Sonnet for classification (fast, cheap)
- Use Claude Sonnet for narrative generation (1 call per user)
- Estimated cost per user: ~$0.10-0.30 depending on cache hit rate

### Supabase
- Free tier supports up to 500MB and 50,000 rows
- A single profile row is ~2-5KB
- video_cache rows are ~500B each
- Free tier is sufficient for thousands of users

### Processing Time
- Cache hits: near-instant
- YouTube API enrichment: ~2-5 seconds for 100 batch calls
- LLM classification: ~10-20 seconds for 80 batch calls
- Narrative generation: ~3-5 seconds
- Total: 15-45 seconds per user (show loading state)

## Privacy Considerations

- We never store raw watch history — only the processed fingerprint and cached video metadata
- The video_cache is global (not user-specific) — it maps videos to topics, not users to videos
- Users can delete their profile at any time
- The share page only shows the fingerprint narrative, dimensions, and hooks — never specific video titles or watch counts
- Be transparent on the upload page: "We process your data to generate your fingerprint, then discard your watch history. We never store what you watched — only what you're into."

## Build Priority Order

1. **Takeout parser** (`lib/fingerprint/parse.ts`) — get this working with a real takeout file
2. **YouTube enrichment** (`lib/fingerprint/enrich.ts`) — batch API calls with caching
3. **LLM classification** (`lib/fingerprint/classify.ts`) — open-ended tagging + clustering
4. **Engagement weighting** (`lib/fingerprint/weight.ts`) — the scoring math
5. **Narrative generation** (`lib/fingerprint/narrate.ts`) — the personality text
6. **Upload page** — dropzone + processing state
7. **Fingerprint display** — the result page
8. **Share card generation** — OG images
9. **Supabase integration** — store profiles + video cache
10. **Homepage + waitlist** — the landing page

## Consequences

- Phase 1 is a standalone product (fingerprint + share) that validates the core thesis before building matching
- The emergent taxonomy approach means the classification system gets smarter as more users join
- Video caching amortizes API costs across users — the more users, the cheaper per-user processing becomes
- The viral share loop means user acquisition and data collection are the same action
- Processing time of 15-45 seconds requires a well-designed loading experience to retain users
- YouTube API quota limits cap daily throughput at ~100 new users/day on the free tier (with caching)
