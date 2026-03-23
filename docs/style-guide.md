# Style Guide — YT Algo Dating App

Derived from the Moment Search landing page aesthetic. This is the design system for the app.

---

## Design Language

**Theme:** Dark mode with cyan/blue accents
**Style:** Modern, minimalist with subtle glassmorphism
**Character:** Premium, tech-forward, editorial elegance

---

## Color Palette

### Backgrounds

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#0F0F0F` | Main page background |
| `bg-elevated` | `#111118` | Card backgrounds, sections |
| `bg-surface` | `#0D0D14` | Nested card backgrounds |
| `bg-surface-hover` | `#141420` | Hover states on surfaces |
| `bg-interactive` | `#1A1A2E` | Interactive areas, mockup panels |
| `bg-input` | `rgba(35, 35, 57, 0.7)` | Input fields (with backdrop blur) |

### Accent Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `accent-primary` | `#00D4FF` | Highlights, CTAs, active states |
| `accent-secondary` | `#0080FF` | Gradients, secondary accents |
| `gradient-primary` | `linear-gradient(135deg, #00D4FF, #0080FF)` | CTA buttons, progress bars, accent lines |

### Text Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `text-primary` | `#F2F2F7` | Headings, important text |
| `text-secondary` | `#7A7A85` | Body text, descriptions |
| `text-tertiary` | `#606078` | Metadata, secondary labels |
| `text-muted` | `#555555` | Faint text |

### Borders

| Token | Value | Usage |
|-------|-------|-------|
| `border-primary` | `#1E1E28` | Dividers, card borders |
| `border-subtle` | `rgba(255, 255, 255, 0.06)` | Very light borders |
| `border-outline` | `#2A2A35` | Outline buttons, secondary borders |
| `border-accent` | `rgba(0, 212, 255, 0.08)` | Decorative accent rings |
| `border-active` | `rgba(74, 111, 165, 0.4)` | Active input borders |

### Status Colors

| Token | Hex |
|-------|-----|
| `status-success` | `#28C840` |
| `status-warning` | `#FEBC2E` |
| `status-error` | `#FF5F57` |

---

## Typography

### Font Families

| Role | Font | Usage |
|------|------|-------|
| **Serif** | `DM Serif Display` (400) | Headlines, hero text |
| **Sans** | `Inter` | Navigation, body text, UI labels |
| **Mono** | `JetBrains Mono` | Technical text, badges, data |

### Scale

| Element | Size | Weight | Letter Spacing | Line Height |
|---------|------|--------|----------------|-------------|
| Hero headline | `clamp(2.8rem, 6.5vw, 5.5rem)` | 400 (serif) | `-0.02em` | `1.05` |
| Hero subtitle | `clamp(1rem, 1.8vw, 1.25rem)` | 400 | normal | `1.7` |
| Section title | `clamp(2rem, 4vw, 3.5rem)` | 400 (serif) | `-0.03em` | `1.1` |
| Feature title | `clamp(1.5rem, 3vw, 2.5rem)` | 400 | normal | `1.2` |
| Section label | `11px` | 400 | `0.2em` | `1` |
| Nav brand | `15px` | 400 | normal | `1` |
| Nav link | `13px` | 400 | `0.02em` | `1` |
| Button text | `15px` | 600 | normal | `1` |
| Body text | `14-16px` | 400 | normal | `1.6` |
| Metadata | `10-12px` | 400 | normal | `1.5` |

---

## Spacing

### Section Padding

| Context | Padding |
|---------|---------|
| Standard section | `120px 48px` |
| Hero | `160px 48px 0` |
| Mobile section | `80px 24px` |
| Footer | `40px 48px` |

### Element Gaps

| Size | Value | Usage |
|------|-------|-------|
| XS | `6-8px` | Tight element groups |
| SM | `12-16px` | Related elements |
| MD | `24-32px` | Card groups, sections |
| LG | `48-64px` | Major section gaps |
| XL | `80px` | Large vertical spacing |

---

## Border Radius

| Element | Radius |
|---------|--------|
| Primary buttons | `0` (sharp) |
| Cards | `8-12px` |
| Input fields | `6-8px` |
| Small UI elements | `4px` |
| Badges/pills | `20px` |
| Decorative orbs | `50%` |

---

## Shadows

| Name | Value | Usage |
|------|-------|-------|
| Glow | `0 8px 32px rgba(0, 212, 255, 0.25)` | CTA hover, accent elements |
| Elevation-md | `0 16px 48px rgba(0, 0, 0, 0.3)` | Floating cards |
| Elevation-lg | `0 32px 80px rgba(0, 0, 0, 0.5)` | Hero elements, mockups |
| Card hover | `0 12px 32px rgba(0, 0, 0, 0.4)` | Card hover state |

---

## Buttons

### Primary (Gradient CTA)

```css
background: linear-gradient(135deg, #00D4FF, #0080FF);
color: #0F0F0F;
padding: 16px 40px;
font-size: 15px;
font-weight: 600;
border-radius: 0;
/* Hover */
transform: translateY(-2px);
box-shadow: 0 8px 32px rgba(0, 212, 255, 0.25);
```

### Outline

```css
background: transparent;
color: #F2F2F7;
border: 1px solid #1E1E28;
padding: 16px 40px;
font-size: 15px;
font-weight: 500;
border-radius: 0;
/* Hover */
border-color: #7A7A85;
background: rgba(255, 255, 255, 0.03);
```

---

## Cards

### Standard Card

```css
background: #0D0D14;
border: 1px solid #1E1E28;
border-radius: 8px;
```

### Featured Card (accent border)

```css
background: #0D0D14;
border: 1px solid rgba(0, 212, 255, 0.15);
border-radius: 8px;
/* Optional top accent bar */
border-top: 3px solid;
border-image: linear-gradient(90deg, #00D4FF, #0080FF) 1;
```

---

## Navigation

```css
position: fixed;
z-index: 100;
height: 64px;
padding: 0 48px;
background: rgba(15, 15, 15, 0.8);
backdrop-filter: blur(12px);
border-bottom: 1px solid #1E1E28;
```

---

## Animations

### Easing

- **Primary:** `cubic-bezier(0.22, 1, 0.36, 1)` — snappy, decelerated
- **Quick:** `0.2s`
- **Standard:** `0.3s`
- **Reveal:** `0.8s`

### Fade Up (scroll reveal)

```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(48px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Stagger delays: 0.1s, 0.25s, 0.4s, 0.55s, 0.7s */
```

### Float (decorative elements)

```css
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-14px); }
}
```

### Slide In (cards/results)

```css
@keyframes slideInCard {
  from { opacity: 0; transform: translateY(16px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
```

---

## Glassmorphism

Used for nav bar, overlays, and input fields:

```css
backdrop-filter: blur(12px);
-webkit-backdrop-filter: blur(12px);
background: rgba(15, 15, 15, 0.8); /* or rgba(35, 35, 57, 0.7) for inputs */
border: 1px solid rgba(255, 255, 255, 0.06);
```

---

## Decorative Elements

### Orbs (background blurs)

```css
position: absolute;
border-radius: 50%;
filter: blur(60px);
pointer-events: none;
/* Cyan: */ background: radial-gradient(circle, rgba(0, 212, 255, 0.08), transparent 70%);
/* Blue: */ background: radial-gradient(circle, rgba(0, 128, 255, 0.06), transparent 70%);
```

### Accent Lines

```css
background: linear-gradient(90deg, transparent, #00D4FF, transparent);
opacity: 0.4;
height: 1px;
```

---

## Responsive Breakpoints

| Breakpoint | Width | Notes |
|------------|-------|-------|
| Desktop | `1024px+` | Full layouts, all features |
| Tablet | `768-1023px` | 2-column grids, reduced padding |
| Mobile | `480-767px` | Single column, `24px` padding, hide decorative elements |
| Small mobile | `<480px` | Compressed layouts |

---

## Selection

```css
::selection {
  background: #00D4FF;
  color: #000;
}
```

## Font Smoothing

```css
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
```

---

## Tech Stack (from Moment Search)

- **Framework:** Next.js
- **Styling:** Tailwind CSS v4
- **Icons:** Lucide React
- **Fonts:** Google Fonts (Inter, DM Serif Display, JetBrains Mono)
