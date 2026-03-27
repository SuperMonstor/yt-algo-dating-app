import { describe, it, expect } from "vitest";
import { parseTakeout, type RawTakeoutEntry } from "../parse";
import fixtureData from "./fixtures/watch-history.json";

const fixture = fixtureData as RawTakeoutEntry[];

describe("parseTakeout", () => {
  const result = parseTakeout(fixture);

  it("returns the correct number of unique videos", () => {
    // 5 unique watchable videos: aBcDeFgHiJk, xXxXxXxXxXx, YyYyYyYyYyY, InDiAsTaRtUp, NoChAnNeL11
    expect(result.stats.uniqueVideos).toBe(5);
  });

  it("counts total entries correctly", () => {
    expect(result.stats.totalEntries).toBe(12);
  });

  it("skips removed videos", () => {
    // 1 removed video (no titleUrl)
    expect(result.stats.skippedRemoved).toBeGreaterThanOrEqual(1);
    const ids = result.videos.map((v) => v.videoId);
    expect(ids).not.toContain(undefined);
  });

  it("skips YouTube Music entries", () => {
    const ids = result.videos.map((v) => v.videoId);
    expect(ids).not.toContain("MuSiCiDxXxX");
  });

  it("skips non-watch URLs", () => {
    // "Visited" entry and "some-other-url" should be filtered
    const titles = result.videos.map((v) => v.title);
    expect(titles).not.toContain("Visited some page");
    expect(titles).not.toContain("Some Ad Video");
  });

  it("deduplicates and counts rewatches", () => {
    const tokyo = result.videos.find((v) => v.videoId === "aBcDeFgHiJk");
    expect(tokyo).toBeDefined();
    expect(tokyo!.watchCount).toBe(2);

    const psychology = result.videos.find((v) => v.videoId === "xXxXxXxXxXx");
    expect(psychology).toBeDefined();
    expect(psychology!.watchCount).toBe(3);
  });

  it("collects all timestamps for rewatched videos", () => {
    const psychology = result.videos.find((v) => v.videoId === "xXxXxXxXxXx");
    expect(psychology!.timestamps).toHaveLength(3);
  });

  it("sorts timestamps newest first", () => {
    const psychology = result.videos.find((v) => v.videoId === "xXxXxXxXxXx");
    const times = psychology!.timestamps.map((t) => t.getTime());
    expect(times).toEqual([...times].sort((a, b) => b - a));
  });

  it("strips 'Watched ' prefix from titles", () => {
    const tokyo = result.videos.find((v) => v.videoId === "aBcDeFgHiJk");
    expect(tokyo!.title).toBe("How Tokyo's Train System Works");
    expect(tokyo!.title).not.toMatch(/^Watched /);
  });

  it("extracts channel name and URL", () => {
    const yc = result.videos.find((v) => v.videoId === "YyYyYyYyYyY");
    expect(yc!.channelName).toBe("Y Combinator");
    expect(yc!.channelUrl).toContain("youtube.com/channel/");
  });

  it("handles missing channel info gracefully", () => {
    const noChannel = result.videos.find((v) => v.videoId === "NoChAnNeL11");
    expect(noChannel).toBeDefined();
    expect(noChannel!.channelName).toBeNull();
    expect(noChannel!.channelUrl).toBeNull();
  });

  it("computes a valid date range", () => {
    expect(result.stats.dateRange).not.toBeNull();
    expect(result.stats.dateRange!.from.getTime()).toBeLessThan(
      result.stats.dateRange!.to.getTime()
    );
  });

  it("handles empty input", () => {
    const empty = parseTakeout([]);
    expect(empty.videos).toHaveLength(0);
    expect(empty.stats.totalEntries).toBe(0);
    expect(empty.stats.dateRange).toBeNull();
  });

  it("handles input where all entries are removed/filtered", () => {
    const allRemoved: RawTakeoutEntry[] = [
      { header: "YouTube", title: "Watched a video that has been removed" },
      { header: "YouTube Music", title: "Watched Song", titleUrl: "https://music.youtube.com/watch?v=abc" },
    ];
    const res = parseTakeout(allRemoved);
    expect(res.videos).toHaveLength(0);
    expect(res.stats.skippedRemoved).toBe(1);
    expect(res.stats.skippedAdsMusic).toBe(1);
  });
});
