# Taste — Build Plan

Each step is independently testable. We verify it works before moving on.

---

## Step 0: Project Scaffolding ✅

Set up the Next.js project with all dependencies configured. No features yet — just a working skeleton we can deploy.

**What to do:**
- `create-next-app` inside a `taste/` directory (App Router, TypeScript, Tailwind)
- Install dependencies: `@supabase/supabase-js`, `@anthropic-ai/sdk`
- Set up `.env.local` with placeholder keys (Supabase, YouTube API, Anthropic)
- Create the Supabase project and run the schema SQL (tables: `profiles`, `video_cache`)
- Minimal `app/page.tsx` that says "Taste" so we can verify the deploy works

**How to test:**
- `npm run dev` starts without errors
- Supabase dashboard shows the tables created
- Deploy to Vercel and see the placeholder page live

---

## Step 1: Takeout Parser ✅

Pure function, zero external dependencies. Parse Google Takeout's `watch-history.json` into a clean array of watch events.

**What to do:**
- Create `lib/fingerprint/parse.ts`
- Parse the JSON array of watch events
- Extract `videoId` from `titleUrl` (regex: `watch\?v=([a-zA-Z0-9_-]{11})`)
- Skip removed videos (entries where `titleUrl` is missing or title says "Watched a video that has been removed")
- Skip ads and YouTube Music entries (filter by URL pattern)
- Deduplicate by videoId but count rewatches and collect all timestamps
- Output: `{ videoId, title, channelName, channelUrl, watchCount, timestamps[] }[]`

**Important detail from Takeout format:**
```json
[
  {
    "header": "YouTube",
    "title": "Watched Some Video Title",
    "titleUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "subtitles": [{ "name": "Channel Name", "url": "https://www.youtube.com/channel/UC..." }],
    "time": "2025-01-15T10:30:00.000Z",
    "products": ["YouTube"],
    "activityControls": ["YouTube watch history"]
  }
]
```

**Note:** Google Takeout can also export as HTML. For MVP, support JSON only (it's the default when you select JSON format in Takeout settings). We can add HTML parsing later if needed.

**How to test:**
- Write a small fixture JSON file with ~20 entries covering edge cases (removed videos, duplicates, music entries, ads)
- Unit test: parse the fixture, assert correct video count, deduplication, rewatch counts
- Unit test: verify removed/ad entries are filtered out
- Can run tests with `npm test` — no API keys needed

---

## Step 2: YouTube API Enrichment

Fetch metadata for videos not already in our cache. This is the first step that hits an external API.

**What to do:**
- Create `lib/fingerprint/enrich.ts`
- Create `lib/youtube.ts` (YouTube Data API v3 helper)
- Accept an array of video IDs, return enriched video objects
- Check `video_cache` table in Supabase first — skip already-cached videos
- Batch uncached videos into groups of 50 (API limit)
- Call `videos.list` with `part=snippet` for each batch
- Extract: `title, channelId, channelTitle, categoryId, tags[], description` (first 200 chars)
- Store results in `video_cache` table
- Track not-found videos (deleted/private) so we don't re-fetch them
- Handle quota errors (HTTP 403) gracefully — save progress and stop

**How to test:**
- Integration test: pass 5 known video IDs, verify we get back metadata with expected fields
- Test cache behavior: run twice with the same IDs, verify second run makes zero API calls
- Test not-found handling: include a fake video ID, verify it's tracked and skipped on retry
- Verify Supabase `video_cache` table has the rows after a run

---

## Step 3: LLM Classification

Tag each video with specific interest dimensions using Claude. No predefined categories — let the LLM generate specific, nuanced tags.

**What to do:**
- Create `lib/fingerprint/classify.ts`
- Accept enriched video objects, return tagged videos with dimension weights
- Batch 20 videos per LLM call (number them in a list)
- System prompt (adapted from the reference PR):
  ```
  You are a content classifier. Given YouTube videos with title, channel, category,
  and tags, classify each one.

  For each video return:
  - tags: 3-5 specific topic tags (lowercase, e.g. "behavioral psychology", "startup funding")
  - weights: corresponding weight for each tag (should sum to ~1.0)

  Be specific — "behavioral psychology" not "science", "Japanese urbanism" not "travel".
  Return a JSON array with one object per video in the same order as input.
  ```
- Parse response, handle multiple JSON formats (array, wrapped object)
- Store classifications in `video_cache` table (`classified_dimensions` column)
- Skip videos already classified (check `classified_at` timestamp)

**How to test:**
- Integration test: pass 5 real enriched video objects, verify we get back tags that make sense
- Test batching: pass 25 videos, verify it makes 2 LLM calls (20 + 5)
- Test cache skip: classify the same videos twice, verify second run makes zero LLM calls
- Test response parsing: mock different response formats, verify all parse correctly

---

## Step 4: Engagement Weighting

Pure math — no external calls. Turn raw watch data + classified videos into a weighted dimension vector.

**What to do:**
- Create `lib/fingerprint/weight.ts`
- Implement `engagementWeight()` function:
  - Rewatch bonus: 2+ watches = 1.5x, 4+ watches = 2.0x
  - Channel depth: 5+ videos from channel = 1.3x, 15+ = 1.6x
  - Late night bonus (11pm-4am): 1.2x
  - Recency bonus (last 90 days): 1.2x
- Aggregate: for each dimension, sum `(video dimension weight × engagement weight)`
- Normalize all scores to 0-1 range (divide by max)
- Return: `{ [dimension: string]: number }` (the fingerprint vector)

**How to test:**
- Unit test with synthetic data: 10 videos with known watch counts, timestamps, and classifications
- Verify rewatch bonus: a video watched 5 times should contribute more than one watched once
- Verify channel depth: videos from a binge-watched channel should score higher
- Verify normalization: max score should be exactly 1.0
- All tests are pure functions — no API keys, no database

---

## Step 5: Hook Extraction

Find what makes this person unique. Pure math against the dimension scores.

**What to do:**
- Create `lib/fingerprint/hooks.ts`
- For Phase 1 (no community data yet), extract hooks based on:
  - **Niche dimensions**: dimensions with moderate-to-high scores that are very specific (multi-word tags like "Japanese city pop" vs generic "music")
  - **Channel-level hooks**: channels the user watched 3+ videos from that are small/niche
  - **Pattern-breakers**: the dimension that correlates least with the user's top dimensions (the guilty pleasure)
- Later (when we have community data): score by inverse frequency
- Return: `{ label, type, score, rarity? }[]`

**How to test:**
- Unit test: given a known dimension vector, verify the correct hooks are extracted
- Test the pattern-breaker detection: give a profile that's 90% tech and 10% reality TV, verify reality TV is flagged
- Pure functions, no external dependencies

---

## Step 6: Narrative Generation

One Claude call that turns the raw numbers into a personality description.

**What to do:**
- Create `lib/fingerprint/narrate.ts`
- Send top dimensions, hooks, top channels, and pattern-breaker to Claude Sonnet
- Prompt asks for:
  1. `primaryIdentity`: 1-2 sentence summary ("You're a curious builder...")
  2. `guiltyPleasure`: playful 1-sentence callout
  3. `dimensionLabels`: human-readable labels for top 6 dimensions
- Parse JSON response
- This is the last pipeline step before display

**How to test:**
- Integration test: pass a realistic profile (can be hardcoded), verify response has all three fields
- Verify `primaryIdentity` is 1-2 sentences, not a paragraph
- Verify `dimensionLabels` has exactly 6 entries
- Test with different profile shapes (tech-heavy, arts-heavy, balanced)

---

## Step 7: Processing API Route

Wire steps 1-6 together into a single endpoint.

**What to do:**
- Create `app/api/process/route.ts`
- Accept multipart/form-data: `file` (watch-history.json) + `name` (display name)
- Run the pipeline in order: parse → enrich → classify → weight → extract hooks → narrate
- Generate a unique `shareSlug` (nanoid, 8 chars)
- Store the profile in Supabase `profiles` table
- Return the full fingerprint JSON
- Handle errors at each stage with clear error messages
- Track processing progress (which stage we're on) for the loading UI

**How to test:**
- Integration test: upload a real (or realistic fixture) watch-history.json via curl/fetch
- Verify the response matches the expected schema
- Verify a row appears in the Supabase `profiles` table
- Test error handling: upload an invalid JSON file, verify clean error message
- Test with a small file (~50 videos) to keep test runs fast

---

## Step 8: Upload UI

The user-facing upload experience.

**What to do:**
- Create `app/upload/page.tsx`
- Step 1: Takeout instructions (how to export from Google Takeout — clear, visual)
- Step 2: File dropzone (drag-and-drop or click to browse) + name input
- Step 3: Processing state — poll the API or use streaming to show progress
  - Fun loading messages: "Reading your 2am rabbit holes...", "Finding your guilty pleasures...", "Building your taste fingerprint..."
- On completion: redirect to `/fingerprint/[slug]`
- Components: `UploadDropzone.tsx`, `ProcessingState.tsx`

**How to test:**
- Manual test: upload a real takeout file, watch the loading states, see the redirect
- Test drag-and-drop and click-to-browse both work
- Test with an invalid file (not JSON, wrong format) — should show a clear error
- Test the loading state transitions feel right (not too fast, not stuck)

---

## Step 9: Fingerprint Display Page

The result page — the thing people screenshot and share.

**What to do:**
- Create `app/fingerprint/[slug]/page.tsx`
- Fetch profile from Supabase via `GET /api/profile/[slug]`
- Create `app/api/profile/[slug]/route.ts` — returns public profile data
- Display:
  - User's name
  - Primary identity narrative
  - Dimension chart (top 6 dimensions as horizontal bars or custom graphic — NOT a pie chart)
  - Hook pills (niche interests as tags)
  - Guilty pleasure callout
  - Stats: total videos processed, date range
- "Share" button (step 10)
- "Get yours" CTA (links to `/upload`)
- "Join the waitlist" CTA below

- Components: `FingerprintDisplay.tsx`, `DimensionChart.tsx`, `HookPills.tsx`

**How to test:**
- Create a test profile in Supabase manually, load the page, verify it renders correctly
- Test with different profile shapes (few dimensions vs many, long name vs short)
- Test the public URL works (anyone with the slug can view it)
- Test OG meta tags are set correctly for link previews (title, description)

---

## Step 10: Share Card Generation

Generate the image people post on Instagram/Twitter.

**What to do:**
- Create `app/api/og/[slug]/route.ts`
- Use `@vercel/og` (Satori) to generate dynamic PNG images
- Two formats:
  - Link preview (1200x630): for Twitter/X, iMessage, WhatsApp
  - Story card (1080x1920): for Instagram stories (add `?format=story` param)
- Card content: name, primary identity, top 5 dimensions as bars, 2-3 hooks as pills, branding
- Set OG meta tags on the fingerprint page pointing to this endpoint
- Create `ShareButton.tsx`: copies link + option to download the story card

**How to test:**
- Hit the OG endpoint directly in the browser — should render a PNG
- Test both formats (default and `?format=story`)
- Share a fingerprint link on Twitter/iMessage — verify the preview card shows up
- Test with long text (long name, long identity sentence) — verify it doesn't overflow

---

## Step 11: Homepage + Waitlist

The entry point and the Phase 2 teaser.

**What to do:**
- Create `app/page.tsx` (homepage):
  - Hero: "Discover your taste fingerprint"
  - 2-3 lines explaining the concept
  - CTA → `/upload`
  - Counter: "N fingerprints generated" (pull count from Supabase)
- Create `app/waitlist/page.tsx`:
  - Email input + submit
  - "We'll notify you when community matching goes live"
- Create `app/api/waitlist/route.ts`:
  - Store email + optional profileId in Supabase
- Add waitlist CTA to the fingerprint result page

**How to test:**
- Verify homepage loads, counter shows correct number
- Submit an email to the waitlist, verify it's stored in Supabase
- Test duplicate email handling (shouldn't create duplicate rows)
- Verify the full user journey: homepage → upload → processing → fingerprint → share → waitlist

---

## What we're NOT building yet

- Clustering / taxonomy normalization (wait until we have data from real users)
- Community matching / weekly intros (Phase 2)
- User accounts / authentication
- Profile deletion (add later, but keep the schema compatible)
- HTML takeout parsing (JSON only for now)
- OAuth-based YouTube data collection (potential future alternative to Takeout)
