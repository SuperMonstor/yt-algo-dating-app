#!/usr/bin/env python3
"""
Beautiful terminal UI for displaying a user's YouTube fingerprint.
"""

import json
import sys
import math
import urllib.request

API_BASE = "http://localhost:8000"

# ── Colors ────────────────────────────────────────────────

class C:
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    DIM      = "\033[2m"
    ITALIC   = "\033[3m"
    # Foreground
    WHITE    = "\033[97m"
    GRAY     = "\033[90m"
    RED      = "\033[91m"
    GREEN    = "\033[92m"
    YELLOW   = "\033[93m"
    BLUE     = "\033[94m"
    MAGENTA  = "\033[95m"
    CYAN     = "\033[96m"
    # Background
    BG_BLACK = "\033[40m"
    BG_GRAY  = "\033[100m"


# ── Helpers ───────────────────────────────────────────────

def bar(value, max_value, width=30, filled_char="━", empty_char="─", color=C.CYAN):
    """Render a horizontal bar."""
    if max_value == 0:
        return C.DIM + empty_char * width + C.RESET
    ratio = min(value / max_value, 1.0)
    filled = int(ratio * width)
    return color + C.BOLD + filled_char * filled + C.RESET + C.DIM + empty_char * (width - filled) + C.RESET


def sparkline(values, width=20):
    """Render a sparkline from values."""
    blocks = " ▁▂▃▄▅▆▇█"
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    return "".join(blocks[min(int((v - mn) / rng * 8), 8)] for v in values[:width])


def format_number(n):
    """Format large numbers (1200 → 1.2K, 1200000 → 1.2M)."""
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1_000:
        return "%.1fK" % (n / 1_000)
    return str(n)


def center(text, width, pad=" "):
    """Center text, accounting for ANSI escape codes."""
    import re
    visible_len = len(re.sub(r'\033\[[0-9;]*m', '', text))
    padding = max(0, width - visible_len)
    left = padding // 2
    right = padding - left
    return pad * left + text + pad * right


def right_align(text, width):
    import re
    visible_len = len(re.sub(r'\033\[[0-9;]*m', '', text))
    padding = max(0, width - visible_len)
    return " " * padding + text


# ── Sections ──────────────────────────────────────────────

W = 72  # Total width

def print_divider(char="─", color=C.DIM):
    print(color + char * W + C.RESET)


def print_header(data):
    personality = data["personality_type"]
    stats = data["watch_stats"]

    print()
    print_divider("━", C.CYAN)
    print()

    # Title
    title = "%s%s  YOUR YOUTUBE FINGERPRINT  %s" % (C.BOLD, C.CYAN, C.RESET)
    print(center(title, W))
    print()

    # Personality badge
    label = personality["label"].upper()
    badge = "%s%s  ◆ %s ◆  %s" % (C.BOLD, C.MAGENTA, label, C.RESET)
    print(center(badge, W))
    print()

    # Description
    desc = personality["description"]
    # Word wrap to W-8
    words = desc.split()
    lines = []
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > W - 8:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    for l in lines:
        print(center("%s%s%s" % (C.DIM, l, C.RESET), W))
    print()

    # Stats row
    vids = "%s%s%s videos" % (C.BOLD, C.WHITE, format_number(stats["total_videos"]))
    channels = "%s%s%s channels" % (C.BOLD, C.WHITE, format_number(stats["unique_channels"]))
    hours = "%s%s%s hours" % (C.BOLD, C.WHITE, "%.0f" % stats["estimated_hours"])

    stats_line = "%s  %s%s  │  %s%s  │  %s%s" % (
        C.GRAY, vids, C.GRAY, channels, C.GRAY, hours, C.RESET
    )
    print(center(stats_line, W))
    print()
    print_divider("━", C.CYAN)


def print_topics(data):
    topics = data["top_topics"]
    if not topics:
        return

    print()
    print("  %s%s TOPICS %s" % (C.BOLD, C.YELLOW, C.RESET))
    print("  %sWhat you watch most%s" % (C.DIM, C.RESET))
    print()

    max_weight = topics[0]["weight"] if topics else 1
    for i, t in enumerate(topics[:12]):
        rank = "%s%2d%s" % (C.DIM, i + 1, C.RESET)
        name = "%-28s" % t["topic"][:28]
        b = bar(t["weight"], max_weight, width=25, color=C.YELLOW)
        val = "%s%6.0f%s" % (C.DIM, t["weight"], C.RESET)
        print("  %s  %s%s%s %s %s" % (rank, C.WHITE, name, C.RESET, b, val))

    print()


def print_channels(data):
    channels = data["top_channels"]
    if not channels:
        return

    print("  %s%s TOP CHANNELS %s" % (C.BOLD, C.CYAN, C.RESET))
    print("  %sYour most-watched creators%s" % (C.DIM, C.RESET))
    print()

    max_weight = channels[0]["weight"] if channels else 1
    for i, ch in enumerate(channels[:12]):
        rank = "%s%2d%s" % (C.DIM, i + 1, C.RESET)
        name = "%-26s" % ch["title"][:26]
        subs = "%s%7s subs%s" % (C.DIM, format_number(ch["subscriber_count"]), C.RESET)
        b = bar(ch["weight"], max_weight, width=16, color=C.CYAN)
        print("  %s  %s%s%s  %s  %s" % (rank, C.WHITE, name, C.RESET, subs, b))

    print()


def print_format(data):
    fmt = data["format_distribution"]
    if not fmt:
        return

    print("  %s%s FORMAT BREAKDOWN %s" % (C.BOLD, C.GREEN, C.RESET))
    print("  %sHow you consume content%s" % (C.DIM, C.RESET))
    print()

    sorted_fmt = sorted(fmt.items(), key=lambda x: x[1], reverse=True)
    max_pct = sorted_fmt[0][1] if sorted_fmt else 1

    colors = [C.GREEN, C.CYAN, C.YELLOW, C.MAGENTA, C.BLUE, C.RED, C.WHITE, C.GRAY]
    for i, (name, pct) in enumerate(sorted_fmt[:8]):
        color = colors[i % len(colors)]
        label = "%-18s" % name[:18]
        pct_str = "%5.1f%%" % (pct * 100)
        b = bar(pct, max_pct, width=30, color=color)
        print("  %s%s%s  %s%s%s  %s" % (C.WHITE, label, C.RESET, C.BOLD, pct_str, C.RESET, b))

    print()


def print_domains(data):
    domains = data["domain_distribution"]
    if not domains:
        return

    print("  %s%s INTEREST MAP %s" % (C.BOLD, C.MAGENTA, C.RESET))
    print("  %sYour world of interests%s" % (C.DIM, C.RESET))
    print()

    # Pie-chart style with unicode blocks
    sorted_doms = list(domains.items())[:10]
    max_pct = max(v for _, v in sorted_doms) if sorted_doms else 1

    icons = ["♫", "⚽", "🎭", "😂", "🧠", "💻", "💼", "🏠", "🎓", "🌍"]
    colors = [C.MAGENTA, C.GREEN, C.CYAN, C.YELLOW, C.BLUE, C.RED, C.WHITE, C.GRAY, C.MAGENTA, C.GREEN]

    for i, (name, pct) in enumerate(sorted_doms):
        icon = icons[i % len(icons)]
        color = colors[i % len(colors)]
        label = "%-16s" % name[:16]
        pct_str = "%5.1f%%" % pct
        b = bar(pct, max_pct, width=28, filled_char="█", empty_char="░", color=color)
        print("  %s %s%s%s  %s%s%s  %s" % (icon, C.WHITE, label, C.RESET, C.BOLD, pct_str, C.RESET, b))

    print()


def print_niche(data):
    niche_ch = data["most_niche_channels"]
    niche_vid = data["most_niche_videos"]

    if not niche_ch and not niche_vid:
        return

    print("  %s%s HIDDEN GEMS %s" % (C.BOLD, C.RED, C.RESET))
    print("  %sThe obscure stuff only you watch%s" % (C.DIM, C.RESET))
    print()

    if niche_ch:
        print("  %sChannels%s" % (C.DIM, C.RESET))
        for ch in niche_ch[:5]:
            subs = format_number(ch["subscriber_count"])
            print("    %s●%s %s%s%s  %s%s subs%s" % (
                C.RED, C.RESET, C.WHITE, ch["title"][:35], C.RESET,
                C.DIM, subs, C.RESET
            ))
        print()

    if niche_vid:
        print("  %sVideos%s" % (C.DIM, C.RESET))
        for v in niche_vid[:5]:
            views = format_number(v["view_count"])
            print("    %s●%s %s%s%s  %s%s views%s" % (
                C.RED, C.RESET, C.WHITE, v["title"][:40], C.RESET,
                C.DIM, views, C.RESET
            ))
        print()


def print_footer(data):
    slug = data["slug"]
    print_divider("─", C.DIM)
    print()
    share = "%s%sShare your fingerprint:%s  %s%s/fingerprint/%s%s" % (
        C.DIM, C.ITALIC, C.RESET, C.CYAN, C.BOLD, slug, C.RESET
    )
    print("  " + share)
    print()
    print_divider("━", C.CYAN)
    print()


# ── Main ──────────────────────────────────────────────────

def fetch_fingerprint():
    try:
        req = urllib.request.Request("%s/fingerprint" % API_BASE)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print("%sError fetching fingerprint: %s%s" % (C.RED, e, C.RESET))
        sys.exit(1)


def main():
    data = fetch_fingerprint()

    print_header(data)
    print_topics(data)
    print_channels(data)
    print_format(data)
    print_domains(data)
    print_niche(data)
    print_footer(data)


if __name__ == "__main__":
    main()
