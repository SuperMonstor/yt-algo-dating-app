/**
 * Enriches parsed video IDs with YouTube API metadata.
 * Cache-first: checks Supabase video_cache before hitting the API.
 * Tracks not-found videos to avoid re-fetching.
 */

import { supabase } from "@/lib/supabase";
import {
  fetchVideoMetadata,
  type YouTubeVideoSnippet,
} from "@/lib/youtube";

export interface EnrichedVideo {
  videoId: string;
  title: string;
  channelId: string;
  channelName: string;
  categoryId: string;
  tags: string[];
  descriptionSnippet: string;
}

export interface EnrichResult {
  videos: EnrichedVideo[];
  stats: {
    total: number;
    cached: number;
    fetched: number;
    notFound: number;
  };
}

/**
 * Look up which video IDs are already in the cache.
 * Returns a map of videoId -> cached data.
 */
async function getCachedVideos(
  videoIds: string[]
): Promise<Map<string, EnrichedVideo>> {
  const cached = new Map<string, EnrichedVideo>();
  if (videoIds.length === 0) return cached;

  // Supabase `in` filter has a limit, batch in groups of 500
  for (let i = 0; i < videoIds.length; i += 500) {
    const batch = videoIds.slice(i, i + 500);
    const { data } = await supabase
      .from("video_cache")
      .select("video_id, title, channel_id, channel_name, yt_category, tags, description_snippet")
      .in("video_id", batch);

    for (const row of data ?? []) {
      cached.set(row.video_id, {
        videoId: row.video_id,
        title: row.title,
        channelId: row.channel_id ?? "",
        channelName: row.channel_name ?? "",
        categoryId: row.yt_category ?? "",
        tags: row.tags ?? [],
        descriptionSnippet: row.description_snippet ?? "",
      });
    }
  }

  return cached;
}

/**
 * Get the set of video IDs already marked as not-found.
 */
async function getNotFoundIds(videoIds: string[]): Promise<Set<string>> {
  const notFoundSet = new Set<string>();
  if (videoIds.length === 0) return notFoundSet;

  for (let i = 0; i < videoIds.length; i += 500) {
    const batch = videoIds.slice(i, i + 500);
    const { data } = await supabase
      .from("videos_not_found")
      .select("video_id")
      .in("video_id", batch);

    for (const row of data ?? []) {
      notFoundSet.add(row.video_id);
    }
  }

  return notFoundSet;
}

/**
 * Store fetched videos in the cache.
 */
async function cacheVideos(videos: YouTubeVideoSnippet[]): Promise<void> {
  if (videos.length === 0) return;

  const rows = videos.map((v) => ({
    video_id: v.videoId,
    title: v.title,
    channel_id: v.channelId,
    channel_name: v.channelTitle,
    yt_category: v.categoryId,
    tags: v.tags,
    description_snippet: v.descriptionSnippet,
  }));

  // Upsert in batches of 500
  for (let i = 0; i < rows.length; i += 500) {
    const batch = rows.slice(i, i + 500);
    await supabase.from("video_cache").upsert(batch, { onConflict: "video_id" });
  }
}

/**
 * Mark video IDs as not-found so we don't re-fetch them.
 */
async function markNotFound(videoIds: string[]): Promise<void> {
  if (videoIds.length === 0) return;

  const rows = videoIds.map((id) => ({ video_id: id }));
  await supabase.from("videos_not_found").upsert(rows, { onConflict: "video_id" });
}

/**
 * Enrich a list of video IDs with YouTube metadata.
 * Cache-first: only fetches videos not already in Supabase.
 */
export async function enrichVideos(videoIds: string[]): Promise<EnrichResult> {
  const apiKey = process.env.YOUTUBE_DATA_API_KEY;
  if (!apiKey) throw new Error("YOUTUBE_DATA_API_KEY is not set");

  // 1. Check cache
  const cached = await getCachedVideos(videoIds);

  // 2. Check not-found list
  const knownNotFound = await getNotFoundIds(videoIds);

  // 3. Figure out what we need to fetch
  const toFetch = videoIds.filter(
    (id) => !cached.has(id) && !knownNotFound.has(id)
  );

  // 4. Fetch from YouTube API
  let fetched: YouTubeVideoSnippet[] = [];
  let newNotFound: string[] = [];

  if (toFetch.length > 0) {
    const result = await fetchVideoMetadata(toFetch, apiKey);
    fetched = result.found;
    newNotFound = result.notFound;

    // 5. Store in cache
    await cacheVideos(fetched);
    await markNotFound(newNotFound);
  }

  // 6. Combine cached + freshly fetched
  const allVideos: EnrichedVideo[] = [];

  for (const id of videoIds) {
    const fromCache = cached.get(id);
    if (fromCache) {
      allVideos.push(fromCache);
      continue;
    }

    const fromApi = fetched.find((v) => v.videoId === id);
    if (fromApi) {
      allVideos.push({
        videoId: fromApi.videoId,
        title: fromApi.title,
        channelId: fromApi.channelId,
        channelName: fromApi.channelTitle,
        categoryId: fromApi.categoryId,
        tags: fromApi.tags,
        descriptionSnippet: fromApi.descriptionSnippet,
      });
    }
    // If not found, it's simply omitted from the result
  }

  return {
    videos: allVideos,
    stats: {
      total: videoIds.length,
      cached: cached.size,
      fetched: fetched.length,
      notFound: knownNotFound.size + newNotFound.length,
    },
  };
}
