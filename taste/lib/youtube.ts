/**
 * YouTube Data API v3 helper.
 * Fetches video metadata in batches of up to 50.
 */

export interface YouTubeVideoSnippet {
  videoId: string;
  title: string;
  channelId: string;
  channelTitle: string;
  categoryId: string;
  tags: string[];
  descriptionSnippet: string;
}

interface YouTubeApiItem {
  id: string;
  snippet?: {
    title?: string;
    channelId?: string;
    channelTitle?: string;
    categoryId?: string;
    tags?: string[];
    description?: string;
  };
}

interface YouTubeApiResponse {
  items?: YouTubeApiItem[];
  error?: {
    code: number;
    message: string;
  };
}

const YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3";
const BATCH_SIZE = 50;

export class YouTubeQuotaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "YouTubeQuotaError";
  }
}

/**
 * Fetch video snippets from YouTube Data API.
 * Batches into groups of 50 (API limit).
 * Returns only the videos that were found.
 */
export async function fetchVideoMetadata(
  videoIds: string[],
  apiKey: string
): Promise<{ found: YouTubeVideoSnippet[]; notFound: string[] }> {
  const found: YouTubeVideoSnippet[] = [];
  const notFound: string[] = [];
  const allRequestedIds = new Set(videoIds);

  for (let i = 0; i < videoIds.length; i += BATCH_SIZE) {
    const batch = videoIds.slice(i, i + BATCH_SIZE);
    const params = new URLSearchParams({
      part: "snippet",
      id: batch.join(","),
      key: apiKey,
    });

    const res = await fetch(`${YOUTUBE_API_BASE}/videos?${params}`);

    if (res.status === 403) {
      throw new YouTubeQuotaError(
        "YouTube API quota exceeded. Progress has been saved."
      );
    }

    if (!res.ok) {
      throw new Error(`YouTube API error: ${res.status} ${res.statusText}`);
    }

    const data: YouTubeApiResponse = await res.json();
    const returnedIds = new Set<string>();

    for (const item of data.items ?? []) {
      returnedIds.add(item.id);
      found.push({
        videoId: item.id,
        title: item.snippet?.title ?? "",
        channelId: item.snippet?.channelId ?? "",
        channelTitle: item.snippet?.channelTitle ?? "",
        categoryId: item.snippet?.categoryId ?? "",
        tags: item.snippet?.tags ?? [],
        descriptionSnippet: (item.snippet?.description ?? "").slice(0, 200),
      });
    }

    // Any IDs in the batch that weren't returned are not found
    for (const id of batch) {
      if (!returnedIds.has(id)) {
        notFound.push(id);
      }
    }

    // Small delay between batches to be polite
    if (i + BATCH_SIZE < videoIds.length) {
      await new Promise((r) => setTimeout(r, 100));
    }
  }

  return { found, notFound };
}
