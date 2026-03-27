/**
 * Parses Google Takeout watch-history.json into clean, deduplicated watch events.
 *
 * Takeout format: array of watch event objects with titleUrl, subtitles, time, etc.
 * Output: deduplicated array with rewatch counts and collected timestamps.
 */

export interface RawTakeoutEntry {
  header?: string;
  title?: string;
  titleUrl?: string;
  subtitles?: { name: string; url: string }[];
  time?: string;
  products?: string[];
  activityControls?: string[];
}

export interface ParsedVideo {
  videoId: string;
  title: string;
  channelName: string | null;
  channelUrl: string | null;
  watchCount: number;
  timestamps: Date[];
}

export interface ParseResult {
  videos: ParsedVideo[];
  stats: {
    totalEntries: number;
    skippedRemoved: number;
    skippedAdsMusic: number;
    uniqueVideos: number;
    totalWatches: number;
    dateRange: { from: Date; to: Date } | null;
  };
}

const VIDEO_ID_REGEX = /[?&]v=([a-zA-Z0-9_-]{11})/;

function extractVideoId(url: string): string | null {
  const match = url.match(VIDEO_ID_REGEX);
  return match ? match[1] : null;
}

function isRemovedVideo(entry: RawTakeoutEntry): boolean {
  if (!entry.titleUrl) return true;
  if (entry.title?.includes("Watched a video that has been removed")) return true;
  return false;
}

function isAdOrMusic(entry: RawTakeoutEntry): boolean {
  const url = entry.titleUrl ?? "";
  if (url.includes("music.youtube.com")) return true;
  if (entry.title?.startsWith("Visited ")) return true;
  if (entry.header === "YouTube Music") return true;
  if (!url.includes("youtube.com/watch")) return true;
  return false;
}

export function parseTakeout(raw: RawTakeoutEntry[]): ParseResult {
  let skippedRemoved = 0;
  let skippedAdsMusic = 0;

  const videoMap = new Map<string, ParsedVideo>();

  for (const entry of raw) {
    if (isRemovedVideo(entry)) {
      skippedRemoved++;
      continue;
    }

    if (isAdOrMusic(entry)) {
      skippedAdsMusic++;
      continue;
    }

    const videoId = extractVideoId(entry.titleUrl!);
    if (!videoId) {
      skippedRemoved++;
      continue;
    }

    const timestamp = entry.time ? new Date(entry.time) : null;

    const existing = videoMap.get(videoId);
    if (existing) {
      existing.watchCount++;
      if (timestamp) existing.timestamps.push(timestamp);
    } else {
      // Title from Takeout is prefixed with "Watched " — strip it
      const title = entry.title?.replace(/^Watched\s+/, "") ?? "";
      const channelName = entry.subtitles?.[0]?.name ?? null;
      const channelUrl = entry.subtitles?.[0]?.url ?? null;

      videoMap.set(videoId, {
        videoId,
        title,
        channelName,
        channelUrl,
        watchCount: 1,
        timestamps: timestamp ? [timestamp] : [],
      });
    }
  }

  const videos = Array.from(videoMap.values());

  // Sort timestamps within each video (newest first)
  for (const video of videos) {
    video.timestamps.sort((a, b) => b.getTime() - a.getTime());
  }

  // Compute date range across all timestamps
  let dateRange: ParseResult["stats"]["dateRange"] = null;
  const allTimestamps = videos.flatMap((v) => v.timestamps);
  if (allTimestamps.length > 0) {
    const sorted = allTimestamps.sort((a, b) => a.getTime() - b.getTime());
    dateRange = { from: sorted[0], to: sorted[sorted.length - 1] };
  }

  return {
    videos,
    stats: {
      totalEntries: raw.length,
      skippedRemoved,
      skippedAdsMusic,
      uniqueVideos: videos.length,
      totalWatches: raw.length - skippedRemoved - skippedAdsMusic,
      dateRange,
    },
  };
}
