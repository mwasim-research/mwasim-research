#!/usr/bin/env python3
"""Draw the profile's cards in assets/ as SVG files, each in a light and a dark version.

  banner     name, overline, tagline and chips from profile.toml, beside a small graph passing messages
  timeline   the research timeline from profile.toml
  activity   contributions over the last 12 months: totals, a calendar heatmap and one bar per month
  languages  share of code by language in the public repositories, overall and per repository
  toolbox    the tools listed in profile.toml

Activity and languages come from the GitHub GraphQL API (public data of the profile owner, read with the
workflow's GITHUB_TOKEN), or from a saved copy for an offline preview (--data). Standard library only,
Python 3.11 or later.

Usage:
    GITHUB_TOKEN=... python .github/scripts/build_cards.py --login mwasim-research
    python .github/scripts/build_cards.py --data preview.json            # offline preview
    python .github/scripts/build_cards.py --config other.toml --only banner --out other/assets
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import tomllib
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
THEMES = {
    "light": {"bg": "#ffffff", "surface": "#f6f8fa", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
              "faint": "#8c959f", "grid": "#e6eaef", "accent": "#bf8700", "teal": "#0f8a7e", "violet": "#8250df",
              "heat": ["#ebeef1", "#b5e4da", "#6fcab9", "#2ea592", "#1a6f63"]},
    "dark": {"bg": "#0d1117", "surface": "#151b23", "border": "#30363d", "text": "#e6edf3", "muted": "#9198a1",
             "faint": "#6e7681", "grid": "#21262d", "accent": "#e3b341", "teal": "#3fc1b0", "violet": "#a371f7",
             "heat": ["#1b222b", "#0f4a46", "#127066", "#22a593", "#58e0c8"]},
}
KINDS = {"paper": ("accent", "Paper"), "code": ("teal", "Code"), "teaching": ("violet", "Teaching")}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
W = 1000

QUERY = """query($login: String!) {
  user(login: $login) {
    login name
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { name stargazerCount
              languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
    }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount weekday } } }
    }
  }
}"""


# ---------------------------------------------------------------- helpers

def tw(s: str, size: float, bold: bool = False) -> float:
    """Approximate rendered width of s in pixels in the usual system sans-serif fonts."""
    units = 0.0
    for c in s:
        if c in "ilIjtf.,:;'|!() ":
            units += 0.30
        elif c in "mwMW@%":
            units += 0.86
        elif c.isupper() or c.isdigit():
            units += 0.64
        else:
            units += 0.53
    return units * size * (1.05 if bold else 1.0)


def text(x, y, s, size, fill, weight=400, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{extra}>{escape(str(s))}</text>')


def svg(width, height, body, title, style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>text{{font-family:{FONT}}}{style}</style>{body}</svg>\n")


def frame(t, w, h):
    return f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{t["bg"]}" stroke="{t["border"]}"/>'


def header(t, title, subtitle=""):
    out = text(32, 46, title, 20, t["text"], 600)
    if subtitle:
        out += text(32 + tw(title, 20, True) + 14, 46, subtitle, 14, t["muted"])
    return out


def ym(s: str) -> dt.date:
    y, m = s.split("-")[:2]
    return dt.date(int(y), int(m), 15)


# ---------------------------------------------------------------- banner

def banner(cfg, t):
    p = cfg["profile"]
    rng = random.Random(int(p.get("seed", 11)))
    nodes, tries = [], 0
    while len(nodes) < 20 and tries < 20000:
        tries += 1
        x, y = rng.uniform(606, 958), rng.uniform(44, 226)
        if all((x - a) ** 2 + (y - b) ** 2 > 46 ** 2 for a, b in nodes):
            nodes.append((x, y))
    edges = set()
    for i, a in enumerate(nodes):
        for j in sorted(range(len(nodes)), key=lambda k: math.dist(a, nodes[k]))[1:3]:
            edges.add((min(i, j), max(i, j)))
    for _ in range(12):
        i, j = rng.sample(range(len(nodes)), 2)
        if 64 < math.dist(nodes[i], nodes[j]) < 130:
            edges.add((min(i, j), max(i, j)))
    # chips: wrap onto a second row rather than run into the graph
    chips, x, row = [], 56.0, 0
    for chip in p.get("chips", []):
        w = tw(chip, 13) + 32
        if x + w > 584 and x > 56:
            x, row = 56.0, row + 1
        chips.append((chip, x, 202 + 38 * row, w))
        x += w + 9
    H = 270 + 38 * row
    deg = [0] * len(nodes)
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    order = sorted(range(len(nodes)), key=lambda i: (-deg[i], nodes[i][0]))
    hubs, mids = order[:3], order[3:8]
    body = [frame(t, W, H),
            '<defs><radialGradient id="glow" cx="790" cy="135" r="290" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{t["teal"]}" stop-opacity="0.16"/>'
            f'<stop offset="1" stop-color="{t["teal"]}" stop-opacity="0"/></radialGradient>'
            '<linearGradient id="fade" x1="560" x2="680" y1="0" y2="0" gradientUnits="userSpaceOnUse">'
            '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>'
            f'<mask id="m"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask></defs>',
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="url(#glow)"/>',
            '<g mask="url(#m)">']
    for i, j in sorted(edges):
        (x1, y1), (x2, y2) = nodes[i], nodes[j]
        body.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}" '
                    'stroke-opacity="0.35" stroke-width="1.2"/>')
    flows = [(i, j) for i, j in sorted(edges) if i in hubs or j in hubs][:9]
    for k, (i, j) in enumerate(flows):
        src, dst = (j, i) if i in hubs else (i, j)  # messages travel into the hub
        (x1, y1), (x2, y2) = nodes[src], nodes[dst]
        colour = t["accent"] if k % 3 == 0 else t["teal"]
        body.append(f'<line class="flow" style="animation-delay:-{0.37 * k:.2f}s" x1="{x1:.1f}" y1="{y1:.1f}" '
                    f'x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colour}" stroke-width="2" stroke-linecap="round"/>')
    for i, (x, y) in enumerate(nodes):
        if i in hubs:
            body.append(f'<circle class="ring" style="animation-delay:-{0.8 * hubs.index(i):.1f}s" cx="{x:.1f}" '
                        f'cy="{y:.1f}" r="8" fill="none" stroke="{t["accent"]}" stroke-width="1.5"/>')
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7.5" fill="{t["accent"]}" stroke="{t["bg"]}" stroke-width="3"/>')
        elif i in mids:
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{t["teal"]}" stroke="{t["bg"]}" stroke-width="2.5"/>')
        else:
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{t["bg"]}" stroke="{t["muted"]}" stroke-width="1.5"/>')
    body.append("</g>")
    body.append(text(56, 94, p.get("overline", "").upper(), 12.5, t["teal"], 600, extra=' letter-spacing="2"'))
    body.append(text(54, 148, p["name"], 50, t["text"], 700, extra=' letter-spacing="-0.5"'))
    body.append(text(56, 182, p.get("tagline", ""), 17.5, t["muted"]))
    dots = [t["teal"], t["accent"], t["violet"]]
    for k, (chip, x, y, w) in enumerate(chips):
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="28" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>')
        body.append(f'<circle cx="{x + 14:.1f}" cy="{y + 14}" r="3.5" fill="{dots[k % 3]}"/>')
        body.append(text(x + 24, y + 18.5, chip, 13, t["text"]))
    style = ("@keyframes flow{to{stroke-dashoffset:-36}}@keyframes ring{from{transform:scale(1);opacity:.6}"
             "to{transform:scale(2.7);opacity:0}}.flow{stroke-dasharray:4 14;stroke-opacity:.9;"
             "animation:flow 1.1s linear infinite}.ring{transform-box:fill-box;transform-origin:center;"
             "animation:ring 2.4s ease-out infinite}@media (prefers-reduced-motion:reduce){.flow,.ring{animation:none}"
             ".ring{opacity:0}}")
    return svg(W, H, "".join(body), f'{p["name"]}: {p.get("tagline", "")}', style)


# ---------------------------------------------------------------- toolbox

def toolbox(cfg, t):
    items = cfg.get("toolbox", {}).get("items", [])
    widths = [tw(s, 14.5) + 40 for s in items]
    rows, row, width = [], [], 0.0
    for s, w in zip(items, widths):
        if row and width + w + 12 > W - 64:
            rows.append(row)
            row, width = [], 0.0
        row.append((s, w))
        width += w + (12 if len(row) > 1 else 0)
    if row:
        rows.append(row)
    H = 20 + 50 * len(rows)
    body, dots = [], [t["teal"], t["accent"], t["violet"]]
    k = 0
    for r, row in enumerate(rows):
        total = sum(w for _, w in row) + 12 * (len(row) - 1)
        x, y = (W - total) / 2, 10 + 50 * r
        for s, w in row:
            body.append(f'<rect x="{x:.1f}" y="{y + 4}" width="{w:.1f}" height="36" rx="18" fill="{t["surface"]}" '
                        f'stroke="{t["border"]}"/>')
            body.append(f'<circle cx="{x + 18:.1f}" cy="{y + 22}" r="4" fill="{dots[k % 3]}"/>')
            body.append(text(x + 29, y + 27, s, 14.5, t["text"], 500))
            x += w + 12
            k += 1
    return svg(W, H, "".join(body), "Toolbox: " + ", ".join(items))


# ---------------------------------------------------------------- timeline

def timeline(cfg, t, today: dt.date):
    items = sorted(cfg.get("timeline", []), key=lambda e: e["date"])
    if not items:
        return None
    left, right = 64, W - 64
    start = ym(items[0]["date"]) - dt.timedelta(days=75)
    end = max(ym(items[-1]["date"]), today) + dt.timedelta(days=75)
    span = (end - start).days

    def xpos(d):
        return left + (right - left) * (d - start).days / span

    # place labels: levels above (-1) and below (+1) the axis, two rows each, first free row wins
    levels = [(-1, 0), (1, 0), (-1, 1), (1, 1)]
    used, placed, conn = {lv: [] for lv in levels}, [], {-1: [], 1: []}
    for e in items:
        d = ym(e["date"])
        x = xpos(d)
        date_s = f"{MONTHS[d.month - 1]} {d.year}"
        width = max(tw(date_s, 13), tw(e["title"], 15, True), tw(e.get("detail", ""), 13))
        if x - width / 2 < 32:
            anchor, x0 = "start", max(32, x - 12)
            x1 = x0 + width
        elif x + width / 2 > W - 32:
            anchor, x1 = "end", min(W - 32, x + 12)
            x0 = x1 - width
        else:
            anchor, x0, x1 = "middle", x - width / 2, x + width / 2
        def free(lv):
            sign, step = lv
            if any(not (x0 > b + 16 or x1 < a - 16) for a, b in used[lv]):
                return False
            if step == 0:  # a second-row connector must not cut through this label
                return all(not (x0 - 8 <= cx <= x1 + 8) for cx in conn[sign])
            return all(not (a - 8 <= x <= b + 8) for a, b in used[(sign, 0)])  # nor this one through a first-row label

        level = next((lv for lv in levels if free(lv)), levels[-1])
        used[level].append((x0, x1))
        if level[1]:
            conn[level[0]].append(x)
        placed.append((e, d, x, date_s, anchor, x0, x1, level))
    up_rows = 1 + any(lv == (-1, 1) for *_, lv in placed)
    down_rows = 1 + any(lv == (1, 1) for *_, lv in placed)
    axis = 70 + 64 * up_rows + 14
    H = axis + 30 + 62 * down_rows + 40

    body = [frame(t, W, H), header(t, "Research timeline")]
    lx = W - 32
    for kind in reversed([k for k in KINDS if any(e.get("kind") == k for e in items)]):
        colour, label = t[KINDS[kind][0]], KINDS[kind][1]
        lx -= tw(label, 13)
        body.append(text(lx, 46, label, 13, t["muted"]))
        lx -= 12
        body.append(f'<circle cx="{lx:.1f}" cy="41.5" r="5" fill="{colour}"/>')
        lx -= 22
    for year in range(start.year + 1, end.year + 1):
        x = xpos(dt.date(year, 1, 1))
        body.append(f'<line x1="{x:.1f}" y1="66" x2="{x:.1f}" y2="{H - 38}" stroke="{t["grid"]}" stroke-dasharray="3 5"/>')
        body.append(text(x, H - 16, year, 12.5, t["faint"], 600, "middle"))
    body.append(f'<line x1="{left - 24}" y1="{axis}" x2="{right + 24}" y2="{axis}" stroke="{t["border"]}" '
                'stroke-width="2" stroke-linecap="round"/>')
    xn = xpos(today)
    body.append(f'<line x1="{xn:.1f}" y1="{axis - 8}" x2="{xn:.1f}" y2="{axis + 8}" stroke="{t["faint"]}" stroke-width="2"/>')
    body.append(text(xn, H - 16, "now", 12.5, t["faint"], 400, "middle"))
    for e, d, x, date_s, anchor, x0, x1, (sign, step) in placed:
        colour = t[KINDS.get(e.get("kind", "code"), KINDS["code"])[0]]
        tx = {"start": x0, "end": x1, "middle": x}[anchor]
        if sign < 0:
            last = axis - 24 - 64 * step
            ys, tip = (last - 36, last - 18, last), last + 7
        else:
            first = axis + 34 + 62 * step
            ys, tip = (first, first + 18, first + 36), first - 14
        body.append(f'<line x1="{x:.1f}" y1="{axis}" x2="{x:.1f}" y2="{tip:.1f}" stroke="{colour}" stroke-opacity="0.6"/>')
        body.append(text(tx, ys[0], date_s, 13, t["muted"], 500, anchor))
        body.append(text(tx, ys[1], e["title"], 15, t["text"], 600, anchor))
        if e.get("detail"):
            body.append(text(tx, ys[2], e["detail"], 13, t["muted"], 400, anchor))
        body.append(f'<circle cx="{x:.1f}" cy="{axis}" r="7" fill="{colour}" stroke="{t["bg"]}" stroke-width="3"/>')
    return svg(W, H, "".join(body), "Research timeline: " + "; ".join(f'{e["date"]} {e["title"]}' for e in items))


# ---------------------------------------------------------------- activity

def activity(user, t, today: dt.date):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = sorted((dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"])
    counts = [c for _, c in days]
    nonzero = sorted(c for c in counts if c)
    total, active = cal["totalContributions"], len(nonzero)
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    best_day, best = max(days, key=lambda dc: (dc[1], dc[0])) if days else (today, 0)
    quart = [nonzero[int(len(nonzero) * q)] for q in (0.25, 0.5, 0.75)] if nonzero else []

    def level(c):
        return 0 if not c else 1 + sum(c > q for q in quart)

    H = 412
    body = [frame(t, W, H), header(t, "Contributions", "last 12 months")]
    stats = [(f"{total:,}", "contributions"), (f"{active}", "active days"), (f"{longest}", "longest streak (days)"),
             (f"{best}", f"busiest day, {best_day.day} {MONTHS[best_day.month - 1]} {best_day.year}" if best else "busiest day")]
    for k, (num, label) in enumerate(stats):
        x = 32 + k * (W - 64) / 4
        body.append(text(x, 104, num, 30, t["accent"] if k == 0 else t["text"], 700))
        body.append(text(x, 128, label, 13.5, t["muted"]))
    body.append(f'<line x1="32" y1="150" x2="{W - 32}" y2="150" stroke="{t["grid"]}"/>')
    lx = W - 32
    body.append(text(lx, 46, "More", 12.5, t["faint"], 400, "end"))
    lx -= tw("More", 12.5) + 8 + 5 * 16
    for k in range(5):
        body.append(f'<rect x="{lx + k * 16:.1f}" y="35" width="12" height="12" rx="3" fill="{t["heat"][k]}"/>')
    body.append(text(lx - 8, 46, "Less", 12.5, t["faint"], 400, "end"))

    pitch, cell = 16, 13
    width = len(weeks) * pitch - (pitch - cell)
    hx0, top = (W - width) / 2 + 16, 188
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body.append(text(hx0 - 9, top + r * pitch + 10, name, 12, t["faint"], 400, "end"))
    month_of_col, labelled = [], -9
    for col, w in enumerate(weeks):
        mid = dt.date.fromisoformat(w["contributionDays"][len(w["contributionDays"]) // 2]["date"])
        month_of_col.append((mid.year, mid.month))
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        starts = col == 0 or any(dt.date.fromisoformat(d["date"]).day == 1 for d in w["contributionDays"])
        if starts and col - labelled >= 3:
            label_day = first if col == 0 else next(dt.date.fromisoformat(d["date"]) for d in w["contributionDays"]
                                                    if dt.date.fromisoformat(d["date"]).day == 1)
            if col == 0 and first.day > 20:
                label_day = None  # too little of that month is shown to label it
            if label_day:
                body.append(text(hx0 + col * pitch, top - 9, MONTHS[label_day.month - 1], 12, t["faint"]))
                labelled = col
        for d in w["contributionDays"]:
            body.append(f'<rect x="{hx0 + col * pitch:.1f}" y="{top + d["weekday"] * pitch}" width="{cell}" height="{cell}" '
                        f'rx="2.5" fill="{t["heat"][level(d["contributionCount"])]}"><title>{d["contributionCount"]} on '
                        f'{d["date"]}</title></rect>')
    month_tot = {}
    for day, c in days:
        month_tot[(day.year, day.month)] = month_tot.get((day.year, day.month), 0) + c
    peak = max(month_tot.values()) if month_tot else 0
    base, tallest = H - 48, 56
    body.append(text(hx0 - 9, base - 1, "Monthly", 12, t["faint"], 400, "end"))
    for key in sorted(set(month_of_col)):
        cols = [c for c, m in enumerate(month_of_col) if m == key]
        x = hx0 + cols[0] * pitch + 1
        w = len(cols) * pitch - (pitch - cell) - 2
        tot = month_tot.get(key, 0)
        h = 3 if not tot else max(6.0, tallest * tot / peak)
        fill = t["grid"] if not tot else t["heat"][4 if tot == peak else 3]
        body.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" fill="{fill}">'
                    f"<title>{tot} in {MONTHS[key[1] - 1]} {key[0]}</title></rect>")
        if tot:
            body.append(text(x + w / 2, base - h - 7, tot, 12, t["muted"], 600, "middle"))
    body.append(text(32, H - 18, f"Updated {today.isoformat()} from the GitHub contribution calendar", 12, t["faint"]))
    return svg(W, H, "".join(body), f"{total} contributions in the last 12 months over {active} active days")


# ---------------------------------------------------------------- languages

def languages(user, t, skip=()):
    repos = [r for r in user["repositories"]["nodes"] if r["name"] not in skip and r["languages"]["edges"]]
    totals, colours = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            totals[name] = totals.get(name, 0) + e["size"]
            colours[name] = e["node"].get("color") or t["faint"]
    if not totals:
        return None
    grand = sum(totals.values())
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    repos.sort(key=lambda r: -sum(e["size"] for e in r["languages"]["edges"]))
    repos = repos[:6]
    H = 176 + 34 * len(repos)
    bx, bw = 300, W - 300 - 140
    body = [frame(t, W, H), header(t, "Languages", "share of code in public repositories"),
            f'<defs><clipPath id="bar"><rect x="32" y="72" width="{W - 64}" height="14" rx="7"/></clipPath></defs>',
            '<g clip-path="url(#bar)">']
    x = 32.0
    for name, size in ranked:
        w = (W - 64) * size / grand
        body.append(f'<rect x="{x:.2f}" y="72" width="{w + 0.5:.2f}" height="14" fill="{colours[name]}"/>')
        x += w
    body.append("</g>")
    x = 32.0
    for name, size in ranked[:6]:
        pct = f"{100 * size / grand:.1f}%"
        body.append(f'<circle cx="{x + 5:.1f}" cy="114" r="5" fill="{colours[name]}"/>')
        body.append(text(x + 16, 119, name, 14, t["text"], 600))
        body.append(text(x + 22 + tw(name, 14, True), 119, pct, 14, t["muted"]))
        x += 22 + tw(name, 14, True) + tw(pct, 14) + 30
    body.append(f'<line x1="32" y1="142" x2="{W - 32}" y2="142" stroke="{t["grid"]}"/>')
    for k, r in enumerate(repos):
        y = 172 + 34 * k
        size = sum(e["size"] for e in r["languages"]["edges"])
        body.append(text(32, y + 5, r["name"], 14, t["text"]))
        body.append(f'<clipPath id="r{k}"><rect x="{bx}" y="{y - 4}" width="{bw}" height="9" rx="4.5"/></clipPath>')
        body.append(f'<g clip-path="url(#r{k})">')
        x = float(bx)
        for e in r["languages"]["edges"]:
            w = bw * e["size"] / size
            body.append(f'<rect x="{x:.2f}" y="{y - 4}" width="{w + 0.5:.2f}" height="9" '
                        f'fill="{e["node"].get("color") or t["faint"]}"/>')
            x += w
        body.append("</g>")
        top = r["languages"]["edges"][0]
        body.append(text(W - 32, y + 5, f'{top["node"]["name"]} {100 * top["size"] / size:.0f}%', 12.5, t["muted"], 400, "end"))
    return svg(W, H, "".join(body), "Languages: " + ", ".join(f"{n} {100 * s / grand:.1f}%" for n, s in ranked[:6]))


# ---------------------------------------------------------------- main

def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.load(resp)
    if out.get("errors"):
        raise SystemExit(f"GraphQL errors: {out['errors']}")
    return out["data"]["user"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--login", default=os.environ.get("PROFILE_LOGIN"), help="GitHub login (default: $PROFILE_LOGIN)")
    ap.add_argument("--data", help="saved user data (JSON, the GraphQL user object) instead of the API")
    ap.add_argument("--config", default=str(ROOT / "profile.toml"))
    ap.add_argument("--out", default=str(ROOT / "assets"))
    ap.add_argument("--only", help="comma-separated cards (banner, toolbox, timeline, activity, languages)")
    ap.add_argument("--today", help="draw as of this date (YYYY-MM-DD), for previews")
    args = ap.parse_args()
    cfg = tomllib.loads(Path(args.config).read_text())
    only = set(args.only.split(",")) if args.only else {"banner", "toolbox", "timeline", "activity", "languages"}
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    user = None
    if only & {"activity", "languages"}:
        user = json.loads(Path(args.data).read_text()) if args.data else fetch(args.login, os.environ["GITHUB_TOKEN"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    login = (user or {}).get("login") or args.login or ""
    for theme, t in THEMES.items():
        cards = {"banner": lambda: banner(cfg, t), "toolbox": lambda: toolbox(cfg, t),
                 "timeline": lambda: timeline(cfg, t, today), "activity": lambda: activity(user, t, today),
                 "languages": lambda: languages(user, t, skip=(login,))}
        for name in sorted(only):
            doc = cards[name]()
            if doc:
                (out / f"{name}-{theme}.svg").write_text(doc)
                print(f"wrote {out / f'{name}-{theme}.svg'}")


if __name__ == "__main__":
    main()
