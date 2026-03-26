#!/usr/bin/env python3
"""
Beautiful terminal UI showing match matrix and detailed breakdowns
for all users in the system.
"""

import json
import asyncio
import asyncpg

DB_URL = "postgresql://postgres:postgres@localhost:5432/ytalgo"

USERS = {
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee": "Dhruv",
    "bbbbbbbb-cccc-dddd-eeee-ffffffffffff": "Nauman",
    "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa": "Tarun",
    "dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb": "Chaitanya",
}


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


W = 76


def bar(value, max_value, width=20, color=C.CYAN):
    if max_value == 0:
        return C.DIM + "─" * width + C.RESET
    ratio = min(value / max_value, 1.0)
    filled = int(ratio * width)
    return color + C.BOLD + "█" * filled + C.RESET + C.DIM + "░" * (width - filled) + C.RESET


def score_color(score):
    s = float(score)
    if s >= 0.4:
        return C.GREEN
    elif s >= 0.2:
        return C.YELLOW
    elif s >= 0.1:
        return C.CYAN
    else:
        return C.DIM


def print_divider(char="─", color=C.DIM):
    print(color + char * W + C.RESET)


async def get_all_data():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    # Get all matches
    async with pool.acquire() as conn:
        matches = await conn.fetch("SELECT * FROM matches ORDER BY score DESC")

        # Get profile summaries
        profiles = {}
        for uid_str, name in USERS.items():
            profile = await conn.fetchrow(
                "SELECT topic_weights, channel_weights, format_distribution, domain_weights, total_long_form_videos FROM user_profiles WHERE user_id = $1::uuid",
                uid_str,
            )
            if profile:
                tw = json.loads(profile["topic_weights"]) if isinstance(profile["topic_weights"], str) else (profile["topic_weights"] or {})
                cw = json.loads(profile["channel_weights"]) if isinstance(profile["channel_weights"], str) else (profile["channel_weights"] or {})
                fd = json.loads(profile["format_distribution"]) if isinstance(profile["format_distribution"], str) else (profile["format_distribution"] or {})
                dw = json.loads(profile["domain_weights"]) if isinstance(profile["domain_weights"], str) else (profile["domain_weights"] or {})
                profiles[name] = {
                    "topics": len(tw),
                    "channels": len(cw),
                    "top_topics": sorted(tw.items(), key=lambda x: x[1], reverse=True)[:5],
                    "top_format": sorted(fd.items(), key=lambda x: x[1], reverse=True)[:3] if fd else [],
                    "total_videos": profile["total_long_form_videos"],
                }

    await pool.close()
    return matches, profiles


def render_header():
    print()
    print(C.CYAN + C.BOLD + "━" * W + C.RESET)
    print()
    title = "%s%s  ⚡ YOUTUBE MATCH MATRIX ⚡  %s" % (C.BOLD, C.CYAN, C.RESET)
    print(title.center(W + 20))
    subtitle = "%s%sWho should hang out based on what they watch%s" % (C.DIM, C.ITALIC, C.RESET)
    print(subtitle.center(W + 16))
    print()
    print(C.CYAN + C.BOLD + "━" * W + C.RESET)


def render_user_cards(profiles):
    print()
    print("  %s%s PLAYERS %s" % (C.BOLD, C.MAGENTA, C.RESET))
    print()

    colors = [C.CYAN, C.GREEN, C.YELLOW, C.MAGENTA]
    for i, (name, p) in enumerate(profiles.items()):
        color = colors[i % len(colors)]
        top_topics_str = ", ".join(t[0] for t in p["top_topics"][:3])
        top_format_str = ", ".join("%s %d%%" % (f[0], f[1] * 100) for f in p["top_format"][:2]) if p["top_format"] else "—"

        print("  %s%s● %s%s%s" % (color, C.BOLD, name.upper(), C.RESET, ""))
        print("    %s%d videos │ %d topics │ %d channels%s" % (
            C.DIM, p["total_videos"], p["topics"], p["channels"], C.RESET
        ))
        print("    %sVibes:%s %s" % (C.DIM, C.RESET, top_topics_str))
        print("    %sFormat:%s %s" % (C.DIM, C.RESET, top_format_str))
        print()


def render_match_matrix(matches):
    print("  %s%s MATCH MATRIX %s" % (C.BOLD, C.YELLOW, C.RESET))
    print("  %sScore = how compatible two people are (0-1)%s" % (C.DIM, C.RESET))
    print()

    # Build score lookup
    scores = {}
    for m in matches:
        a = str(m["user_id_a"])
        b = str(m["user_id_b"])
        name_a = USERS.get(a, a[:8])
        name_b = USERS.get(b, b[:8])
        scores[(name_a, name_b)] = float(m["score"])
        scores[(name_b, name_a)] = float(m["score"])

    names = list(USERS.values())

    # Header row
    header = "  %-12s" % ""
    for n in names:
        header += " %s%-10s%s" % (C.BOLD, n[:10], C.RESET)
    print(header)
    print("  " + "─" * (12 + 10 * len(names)))

    # Matrix rows
    for row_name in names:
        row = "  %s%-12s%s" % (C.WHITE, row_name, C.RESET)
        for col_name in names:
            if row_name == col_name:
                row += " %s%-10s%s" % (C.DIM, "  ·····", C.RESET)
            else:
                score = scores.get((row_name, col_name), 0)
                color = score_color(score)
                row += " %s%s%-10s%s" % (color, C.BOLD, "  %.3f" % score, C.RESET)
        print(row)

    print()


def render_rankings(matches):
    print("  %s%s MATCH RANKINGS %s" % (C.BOLD, C.GREEN, C.RESET))
    print("  %sBest matches across all users%s" % (C.DIM, C.RESET))
    print()

    medal = ["🥇", "🥈", "🥉", " 4", " 5", " 6"]
    seen = set()

    for i, m in enumerate(matches):
        a = str(m["user_id_a"])
        b = str(m["user_id_b"])
        name_a = USERS.get(a, a[:8])
        name_b = USERS.get(b, b[:8])
        pair = tuple(sorted([name_a, name_b]))
        if pair in seen:
            continue
        seen.add(pair)

        score = float(m["score"])
        color = score_color(score)
        icon = medal[min(i, len(medal) - 1)]

        b_bar = bar(score, 1.0, width=25, color=color)
        print("  %s  %s%s%s × %s%s%s  %s%.3f%s  %s" % (
            icon,
            C.WHITE + C.BOLD, name_a, C.RESET,
            C.WHITE + C.BOLD, name_b, C.RESET,
            color + C.BOLD, score, C.RESET,
            b_bar,
        ))

    print()


def render_match_detail(m, rank):
    a = str(m["user_id_a"])
    b = str(m["user_id_b"])
    name_a = USERS.get(a, a[:8])
    name_b = USERS.get(b, b[:8])
    score = float(m["score"])
    details = json.loads(m["details"]) if isinstance(m["details"], str) else (m["details"] or {})

    color = score_color(score)

    print_divider("─", C.DIM)
    print()
    print("  %s%s%s%s × %s%s%s  —  Score: %s%s%.3f%s" % (
        C.WHITE, C.BOLD, name_a, C.RESET,
        C.WHITE + C.BOLD, name_b, C.RESET,
        color, C.BOLD, score, C.RESET,
    ))
    print()

    # Signal breakdown
    signals = [
        ("Topic Overlap", float(m["topic_overlap"] or 0), 0.35, C.YELLOW),
        ("Embedding Sim", float(m["embedding_sim"] or 0), 0.25, C.CYAN),
        ("Channel Overlap", float(m["channel_overlap"] or 0), 0.20, C.GREEN),
        ("Domain Match", float(m["domain_sim"] or 0), 0.10, C.MAGENTA),
        ("Format Match", float(m["format_sim"] or 0), 0.05, C.BLUE),
        ("Complementary", float(m["complementary"] or 0), 0.05, C.RED),
    ]

    print("  %sSignal Breakdown:%s" % (C.DIM, C.RESET))
    for name, val, weight, color in signals:
        weighted = val * weight
        b = bar(val, 1.0, width=20, color=color)
        print("    %-18s %s  %s%.3f%s  ×%.2f = %s%.4f%s" % (
            name, b, color, val, C.RESET, weight, C.BOLD, weighted, C.RESET,
        ))
    print()

    # What they share
    shared_topics = details.get("shared_topics", [])
    shared_channels = details.get("shared_channels", [])
    complementary = details.get("complementary_topics", [])
    seed = details.get("conversation_seed")

    if shared_topics:
        print("  %s%s🔗 What connects them:%s" % (C.BOLD, C.GREEN, C.RESET))
        topics_str = ", ".join(t["topic"] for t in shared_topics[:8])
        print("    %sTopics:%s %s" % (C.DIM, C.RESET, topics_str))

    if shared_channels:
        channels_str = ", ".join(c["title"] for c in shared_channels[:5])
        print("    %sChannels:%s %s" % (C.DIM, C.RESET, channels_str))

    if complementary:
        print()
        print("  %s%s🔀 Could learn from each other:%s" % (C.BOLD, C.MAGENTA, C.RESET))
        for c in complementary[:3]:
            you_label = "deep" if c.get("you") == "deep" else "exploring"
            them_label = "deep" if c.get("them") == "deep" else "exploring"
            print("    %s%-25s%s  %s: %s%s%s  %s: %s%s%s" % (
                C.WHITE, c["topic"][:25], C.RESET,
                name_a, C.BOLD, you_label, C.RESET,
                name_b, C.BOLD, them_label, C.RESET,
            ))

    if seed:
        print()
        print("  %s%s💬 Conversation starter:%s" % (C.BOLD, C.CYAN, C.RESET))
        print("    %s\"%s\"%s" % (C.ITALIC, seed.get("prompt", ""), C.RESET))

    print()


def render_what_makes_unique(profiles):
    print_divider("─", C.DIM)
    print()
    print("  %s%s 🎯 WHAT MAKES EACH PERSON UNIQUE %s" % (C.BOLD, C.RED, C.RESET))
    print()

    colors = [C.CYAN, C.GREEN, C.YELLOW, C.MAGENTA]
    unique_vibes = {
        "Dhruv": "Music polymath — reggaeton, EDM, indie pop, AR Rahman. Australian Open tennis. HealthyGamerGG depth. Running culture.",
        "Nauman": "Bollywood soul — AR Rahman devotee, Kannada cinema explorer, Hindi romantic songs. Pure music identity.",
        "Tarun": "Sidemen universe — KSI, Beta Squad, football challenges. UK YouTube culture + Kannada roots + luxury watches.",
        "Chaitanya": "Electronic underground — Anjunadeep, psytrance festivals, Astrix. Geopolitics analyst. Most niche of the group.",
    }

    for i, (name, vibe) in enumerate(unique_vibes.items()):
        color = colors[i % len(colors)]
        print("  %s%s● %s%s" % (color, C.BOLD, name, C.RESET))
        # Word wrap
        words = vibe.split()
        line = "    "
        for word in words:
            if len(line) + len(word) + 1 > W - 4:
                print("%s%s%s" % (C.DIM, line, C.RESET))
                line = "    " + word
            else:
                line = line + " " + word if line.strip() else "    " + word
        if line.strip():
            print("%s%s%s" % (C.DIM, line, C.RESET))
        print()


def render_verdict(matches):
    print_divider("━", C.CYAN)
    print()
    print("  %s%s ⚡ THE VERDICT %s" % (C.BOLD, C.CYAN, C.RESET))
    print()

    # Find best match
    seen = set()
    best = None
    for m in matches:
        a = str(m["user_id_a"])
        b = str(m["user_id_b"])
        pair = tuple(sorted([USERS.get(a, a), USERS.get(b, b)]))
        if pair not in seen:
            seen.add(pair)
            if best is None:
                best = (pair, float(m["score"]))

    if best:
        print("  %s%sBest match: %s × %s (%.3f)%s" % (
            C.GREEN, C.BOLD, best[0][0], best[0][1], best[1], C.RESET
        ))

    # Find most unique pair (lowest score)
    all_pairs = []
    seen2 = set()
    for m in matches:
        a = str(m["user_id_a"])
        b = str(m["user_id_b"])
        pair = tuple(sorted([USERS.get(a, a), USERS.get(b, b)]))
        if pair not in seen2:
            seen2.add(pair)
            all_pairs.append((pair, float(m["score"])))

    if all_pairs:
        worst = min(all_pairs, key=lambda x: x[1])
        print("  %s%sMost different: %s × %s (%.3f)%s" % (
            C.RED, C.BOLD, worst[0][0], worst[0][1], worst[1], C.RESET
        ))

    print()

    # Fun insights
    print("  %s%s💡 Insights:%s" % (C.BOLD, C.YELLOW, C.RESET))
    print("  %s• Dhruv & Nauman bond over Bollywood + music — the strongest signal%s" % (C.DIM, C.RESET))
    print("  %s• Tarun lives in the Sidemen universe — unique among the group%s" % (C.DIM, C.RESET))
    print("  %s• Chaitanya's electronic music + geopolitics is the most niche combo%s" % (C.DIM, C.RESET))
    print("  %s• All 4 share some Indian content DNA — but express it very differently%s" % (C.DIM, C.RESET))
    print()
    print(C.CYAN + C.BOLD + "━" * W + C.RESET)
    print()


async def main():
    matches, profiles = await get_all_data()

    render_header()
    render_user_cards(profiles)
    render_match_matrix(matches)
    render_rankings(matches)

    # Detailed breakdowns for unique pairs
    print("  %s%s DETAILED BREAKDOWNS %s" % (C.BOLD, C.CYAN, C.RESET))

    seen = set()
    for m in matches:
        a = str(m["user_id_a"])
        b = str(m["user_id_b"])
        pair = tuple(sorted([a, b]))
        if pair not in seen:
            seen.add(pair)
            render_match_detail(m, len(seen))

    render_what_makes_unique(profiles)
    render_verdict(matches)


if __name__ == "__main__":
    asyncio.run(main())
