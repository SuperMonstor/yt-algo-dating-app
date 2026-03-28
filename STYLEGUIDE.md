# Taste — Style Guide

Visual language for all Taste UI. Brutalist, data-dense, dark.

---

## Aesthetic

**Stark brutalist.** Black backgrounds, sharp edges, no border-radius, no gradients, no shadows. Data is the decoration. Density over whitespace. Grid-heavy layouts. Typography does the heavy lifting.

---

## Colors

| Token | Hex | Usage |
|-------|-----|-------|
| **Background** | `#000000` | Page background, always pure black |
| **Surface** | `bg-zinc-900` | Bars, empty states, card backgrounds |
| **Surface raised** | `bg-zinc-950` | Slightly elevated cards when needed |
| **Accent** | `#ff4d00` | Primary accent — scores, highlights, CTAs, avatar bg, badges |
| **Text primary** | `#ffffff` | Headings, names, stats values |
| **Text secondary** | `text-zinc-300` | Body text, dimension labels |
| **Text tertiary** | `text-zinc-400` | Descriptions, identity narrative |
| **Text muted** | `text-zinc-600` | Section labels, metadata, timestamps |
| **Border** | `border-zinc-900` | Section dividers, stats bar borders |
| **Border pill** | `border-zinc-700` | Hook/tag pill borders |

**Rules:**
- Never use gradients on backgrounds or bars
- Accent color is only `#ff4d00` — no secondary accent
- Channel tiles use their own brand color as background with black text
- Badges (rewatch count, etc.) use accent bg with black text

---

## Typography

**Font:** Geist Sans (`font-sans`) for everything. No serif, no mono.

| Element | Classes |
|---------|---------|
| **Page title (name)** | `text-6xl font-black tracking-tighter leading-[0.85]` |
| **Stat values** | `text-2xl font-black` (in stats bar), `text-xl font-black text-[#ff4d00]` (inline scores) |
| **Body text** | `text-base leading-relaxed text-zinc-400` |
| **Section labels** | `text-xs text-zinc-600 uppercase tracking-wider` |
| **Brand label** | `text-xs text-[#ff4d00] tracking-[0.3em] uppercase` |
| **Pill/tag text** | `text-xs font-bold uppercase tracking-wider` |
| **Thumbnail caption** | `text-[11px] font-medium leading-tight` |
| **Thumbnail metadata** | `text-[10px] text-zinc-600` |
| **Badge text** | `text-[10px] font-black` |

**Rules:**
- Headings are always `font-black` (900 weight)
- Section labels are always uppercase with `tracking-wider`
- No font sizes between 3xl and 6xl — jump from data to display
- Trailing period on the name uses accent color: `<span className="text-[#ff4d00]">.</span>`

---

## Layout

- **Max width:** `max-w-4xl` (container)
- **Page padding:** `px-6 pt-20 pb-32`
- **Section spacing:** `mb-16` between major sections
- **Grid gaps:** `gap-1` for visual grids (channels, thumbnails), `gap-8` for content grids (dimensions)
- **Responsive columns:** Mobile-first, `sm:` breakpoint for desktop layouts

**Grid patterns used:**
- Channel tiles: `grid-cols-3 sm:grid-cols-6 gap-1` (square aspect ratio)
- Dimensions: `sm:grid-cols-2 gap-x-8 gap-y-4`
- Thumbnails: `grid-cols-2 sm:grid-cols-4 gap-1`
- Side-by-side content: `sm:grid-cols-2 gap-8`
- Stats: flex with `justify-between`

---

## Components

### Avatar
Square, no border-radius. Accent background with initial in `font-black text-black`.
```
h-36 w-36 bg-[#ff4d00] flex items-center justify-center
```

### Channel Tile
Square aspect ratio. Brand-colored background. Black text.
```
aspect-square flex flex-col items-center justify-center
Initial: text-3xl sm:text-4xl font-black text-black
Name: text-[9px] font-bold text-black/60 uppercase tracking-wider
Count: text-xs font-black text-black/80
```

### Dimension Bar
Label left, score right, thin bar below.
```
Bar track: h-2 bg-zinc-900
Bar fill: h-full bg-[#ff4d00], width set by score
Score: text-xl font-black text-[#ff4d00]
Label: text-sm text-zinc-300
```

### Thumbnail Card
Aspect-video image with top-right badge overlay.
```
Container: relative aspect-video bg-zinc-900
Badge: absolute top-0 right-0 bg-[#ff4d00] text-black px-1.5 py-0.5 text-[10px] font-black
Caption below image, not overlaid.
```

### Hook Pill
Rectangular, no border-radius. Zinc border.
```
border border-zinc-700 px-3 py-1.5 text-xs font-bold uppercase tracking-wider
```

### Primary CTA
Accent background, black text, no border-radius.
```
bg-[#ff4d00] px-6 py-3 text-sm font-black uppercase tracking-widest text-black
```

### Secondary CTA
White border, white text, no border-radius.
```
border-2 border-white px-6 py-3 text-sm font-black uppercase tracking-widest
```

### Stats Bar
Bordered top and bottom. Flex row, justified between.
```
border-t border-b border-zinc-900 py-6
Value: text-2xl font-black
Label: text-[10px] text-zinc-600 uppercase tracking-wider
```

---

## Principles

1. **No border-radius anywhere.** Everything is sharp rectangles.
2. **Data is visual.** Channel colors, score bars, and thumbnail grids replace illustration.
3. **Dense over spacious.** Pack information tight. 1px gaps between grid items.
4. **Two weights only.** `font-black` (900) for emphasis, default weight for body. No medium, semibold, etc.
5. **Uppercase labels, mixed-case content.** Section headers scream, body text speaks.
6. **Images earn their space.** Every image is data (YouTube thumbnail, channel identity) — no decorative imagery.
7. **One accent color.** `#ff4d00` is the only pop of color besides channel brand colors.
