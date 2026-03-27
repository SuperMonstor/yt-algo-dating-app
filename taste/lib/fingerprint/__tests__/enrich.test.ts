import { describe, it, expect } from "vitest";
import { enrichVideos } from "../enrich";

// These are real, stable YouTube video IDs (popular videos unlikely to be deleted)
const KNOWN_VIDEO_IDS = [
  "dQw4w9WgXcQ", // Rick Astley - Never Gonna Give You Up
  "jNQXAC9IVRw", // Me at the zoo (first YouTube video)
  "9bZkp7q19f0", // PSY - Gangnam Style
];

const FAKE_VIDEO_ID = "xxxxxxxxxxx"; // should not exist

describe("enrichVideos", () => {
  it("fetches metadata for known videos", async () => {
    const result = await enrichVideos(KNOWN_VIDEO_IDS);

    expect(result.videos.length).toBe(KNOWN_VIDEO_IDS.length);
    expect(result.stats.total).toBe(KNOWN_VIDEO_IDS.length);

    for (const video of result.videos) {
      expect(video.videoId).toBeTruthy();
      expect(video.title).toBeTruthy();
      expect(video.channelId).toBeTruthy();
      expect(video.channelName).toBeTruthy();
    }
  }, 30000);

  it("returns cached results on second call (no new API fetches)", async () => {
    const result = await enrichVideos(KNOWN_VIDEO_IDS);

    expect(result.stats.cached).toBe(KNOWN_VIDEO_IDS.length);
    expect(result.stats.fetched).toBe(0);
    expect(result.videos.length).toBe(KNOWN_VIDEO_IDS.length);
  }, 15000);

  it("handles not-found videos gracefully", async () => {
    const ids = [...KNOWN_VIDEO_IDS, FAKE_VIDEO_ID];
    const result = await enrichVideos(ids);

    // Should return only the real videos
    expect(result.videos.length).toBe(KNOWN_VIDEO_IDS.length);
    expect(result.stats.notFound).toBeGreaterThanOrEqual(1);
  }, 15000);

  it("skips known not-found videos on subsequent calls", async () => {
    const result = await enrichVideos([FAKE_VIDEO_ID]);

    expect(result.videos.length).toBe(0);
    expect(result.stats.notFound).toBe(1);
    expect(result.stats.fetched).toBe(0); // didn't re-fetch
  }, 15000);
});
