// V3C: Brutalist + grid-heavy, channel tiles as main visual, compact dense layout
import { mockProfile } from "@/lib/mock-fingerprint";

export default function V3C() {
  const p = mockProfile;

  return (
    <div className="min-h-screen bg-black text-white font-sans">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex gap-2 px-4 py-2 text-xs bg-black/90">
        {["3", "3b", "3c", "3d", "3e"].map((n) => (
          <a key={n} href={`/demo/v${n}`} className={`px-2 py-1 ${n === "3c" ? "text-[#ff4d00]" : "text-zinc-600"}`}>
            V{n.toUpperCase()}
          </a>
        ))}
      </nav>

      <div className="mx-auto max-w-4xl px-6 pt-20 pb-32">
        {/* Compact header — avatar + name + identity side by side */}
        <div className="mb-16 flex flex-col gap-6 sm:flex-row sm:items-start sm:gap-10">
          <div className="shrink-0">
            <div className="h-36 w-36 bg-[#ff4d00] flex items-center justify-center">
              <span className="text-7xl font-black text-black">{p.name[0]}</span>
            </div>
          </div>
          <div className="flex-1">
            <p className="text-[#ff4d00] text-xs tracking-[0.3em] uppercase mb-2">Taste</p>
            <h1 className="text-6xl font-black tracking-tighter leading-[0.85] mb-4">
              {p.name}<span className="text-[#ff4d00]">.</span>
            </h1>
            <p className="text-base leading-relaxed text-zinc-400 max-w-md">
              {p.primaryIdentity}
            </p>
          </div>
        </div>

        {/* Channel grid — large colored tiles as main visual */}
        <section className="mb-16">
          <p className="text-xs text-zinc-600 uppercase tracking-wider mb-4">Top Channels</p>
          <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
            {p.topChannels.map((ch) => (
              <div
                key={ch.name}
                className="aspect-square flex flex-col items-center justify-center p-2 text-center"
                style={{ backgroundColor: ch.color }}
              >
                <span className="text-3xl font-black text-black sm:text-4xl">{ch.initial}</span>
                <span className="text-[9px] font-bold text-black/60 uppercase tracking-wider mt-1 leading-tight">
                  {ch.name}
                </span>
                <span className="text-xs font-black text-black/80 mt-0.5">{ch.count}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Dimensions — compact two-column grid */}
        <section className="mb-16">
          <p className="text-xs text-zinc-600 uppercase tracking-wider mb-4">Dimensions</p>
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {p.dimensions.map((d) => (
              <div key={d.label}>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="text-sm text-zinc-300">{d.label}</span>
                  <span className="text-xl font-black text-[#ff4d00]">{(d.score * 100).toFixed(0)}</span>
                </div>
                <div className="h-2 w-full bg-zinc-900">
                  <div className="h-full bg-[#ff4d00]" style={{ width: `${d.score * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Rewatched — thumbnail grid */}
        <section className="mb-16">
          <p className="text-xs text-zinc-600 uppercase tracking-wider mb-4">On Repeat</p>
          <div className="grid gap-1 grid-cols-2 sm:grid-cols-4">
            {p.topRewatched.map((v) => (
              <div key={v.videoId}>
                <div className="relative aspect-video bg-zinc-900">
                  <img
                    src={`https://img.youtube.com/vi/${v.videoId}/mqdefault.jpg`}
                    alt={v.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-0 right-0 bg-[#ff4d00] text-black px-1.5 py-0.5 text-[10px] font-black">
                    {v.watches}x
                  </div>
                </div>
                <p className="text-[11px] font-medium mt-1 leading-tight">{v.title}</p>
                <p className="text-[10px] text-zinc-600">{v.channel}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Hooks + Guilty Pleasure — side by side */}
        <section className="mb-16 grid gap-8 sm:grid-cols-2">
          <div>
            <p className="text-xs text-zinc-600 uppercase tracking-wider mb-4">Niche Signals</p>
            <div className="flex flex-wrap gap-2">
              {p.hooks.map((h) => (
                <span
                  key={h.label}
                  className="border border-zinc-700 px-3 py-1.5 text-xs font-bold uppercase tracking-wider"
                >
                  {h.label}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-[#ff4d00] uppercase tracking-wider mb-4">Pattern Breaker</p>
            <p className="text-sm text-zinc-400 leading-relaxed">{p.guiltyPleasure}</p>
          </div>
        </section>

        {/* Stats bar */}
        <section className="mb-16 border-t border-b border-zinc-900 py-6">
          <div className="flex flex-wrap justify-between gap-4">
            {[
              { label: "Videos", value: p.stats.totalVideos.toLocaleString() },
              { label: "Channels", value: p.stats.uniqueChannels.toString() },
              { label: "Daily Avg", value: p.stats.avgPerDay.toString() },
              { label: "Rewatch", value: `${(p.stats.rewatchRate * 100).toFixed(0)}%` },
              { label: "Night Owl", value: `${(p.stats.lateNightPercent * 100).toFixed(0)}%` },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-2xl font-black">{s.value}</p>
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTAs */}
        <div className="flex gap-3">
          <button className="bg-[#ff4d00] px-6 py-3 text-sm font-black uppercase tracking-widest text-black">
            Share
          </button>
          <button className="border-2 border-white px-6 py-3 text-sm font-black uppercase tracking-widest">
            Get Yours
          </button>
        </div>
      </div>
    </div>
  );
}
