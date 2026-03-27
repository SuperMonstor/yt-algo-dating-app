export const mockProfile = {
  name: "Arjun",
  slug: "arj-x8k2m",
  avatar: "/mock/avatar.jpg",
  primaryIdentity:
    "You're a systems thinker who treats YouTube like a graduate seminar — bouncing between startup deep-dives, cognitive science lectures, and the occasional 3AM lo-fi coding stream.",
  guiltyPleasure:
    "For someone who watches 40 hours of tech talks a month, you spend a suspicious amount of time on Indian street food videos.",
  dimensions: [
    { label: "Startup & Venture", score: 0.92 },
    { label: "Cognitive Science", score: 0.78 },
    { label: "Software Engineering", score: 0.71 },
    { label: "Urban Design", score: 0.54 },
    { label: "Electronic Music", score: 0.43 },
    { label: "Indian Street Food", score: 0.38 },
  ],
  hooks: [
    { label: "mechanism design", type: "niche" as const },
    { label: "Japanese city planning", type: "niche" as const },
    { label: "modular synthesis", type: "niche" as const },
    { label: "founder psychology", type: "channel" as const },
    { label: "biomimicry", type: "niche" as const },
    { label: "Bayesian reasoning", type: "niche" as const },
    { label: "transit urbanism", type: "niche" as const },
  ],
  topChannels: [
    { name: "Y Combinator", count: 127, initial: "YC", color: "#ff4d00" },
    { name: "Lex Fridman", count: 89, initial: "LF", color: "#3b82f6" },
    { name: "3Blue1Brown", count: 64, initial: "3B", color: "#2563eb" },
    { name: "Not Just Bikes", count: 52, initial: "NB", color: "#16a34a" },
    { name: "Fireship", count: 48, initial: "FS", color: "#f59e0b" },
    { name: "Veritasium", count: 41, initial: "Ve", color: "#8b5cf6" },
  ],
  topRewatched: [
    { title: "How to Get Rich (Naval)", channel: "Lex Fridman", watches: 7, videoId: "3qHkcs3kG44" },
    { title: "The Unreasonable Effectiveness of Mathematics", channel: "Veritasium", watches: 5, videoId: "fNk_zzaMoSs" },
    { title: "Why City Design is Important", channel: "Not Just Bikes", watches: 5, videoId: "uxykI30fS54" },
    { title: "Startup Ideas No One Is Building", channel: "Y Combinator", watches: 4, videoId: "uvw-u99yj8w" },
  ],
  stats: {
    totalVideos: 4832,
    dateRange: { from: "Jan 2019", to: "Mar 2026" },
    rewatchRate: 0.12,
    lateNightPercent: 0.34,
    uniqueChannels: 342,
    avgPerDay: 1.8,
  },
};
