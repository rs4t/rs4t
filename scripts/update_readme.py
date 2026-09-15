#!/usr/bin/env python3
"""Fetch GitHub stats for rs4t and rewrite the neofetch-style block in README.md."""
import os
import sys
import datetime
import hashlib
import urllib.request
import json
import base64

USERNAME = "rs4t"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def api_get(path, params=None):
    url = f"{API}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode()), dict(resp.headers)


def paginate(path, params=None):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    items = []
    while True:
        params["page"] = page
        data, _ = api_get(path, params)
        if not data:
            break
        items.extend(data)
        if len(data) < params["per_page"]:
            break
        page += 1
    return items


def get_user():
    data, _ = api_get(f"/users/{USERNAME}")
    return data


def get_repos():
    return paginate(f"/users/{USERNAME}/repos", {"type": "owner"})


def get_total_stars(repos):
    return sum(r.get("stargazers_count", 0) for r in repos)


def get_total_commits(repos):
    total = 0
    for r in repos:
        if r.get("fork"):
            continue
        full_name = r["full_name"]
        try:
            _, headers = api_get(
                f"/repos/{full_name}/commits",
                {"author": USERNAME, "per_page": 1},
            )
            link = headers.get("Link", "")
            if 'rel="last"' in link:
                # parse last page number from Link header
                last_part = [p for p in link.split(",") if 'rel="last"' in p][0]
                page_str = last_part.split("page=")[-1].split(">")[0].split("&")[0]
                total += int(page_str)
            else:
                data, _ = api_get(
                    f"/repos/{full_name}/commits",
                    {"author": USERNAME, "per_page": 100},
                )
                total += len(data)
        except Exception:
            continue
    return total


def get_top_languages(repos):
    totals = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            data, _ = api_get(f"/repos/{r['full_name']}/languages")
        except Exception:
            continue
        for lang, count in data.items():
            totals[lang] = totals.get(lang, 0) + count
    grand_total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:4]
    return [(lang, 100 * count / grand_total) for lang, count in top]


def uptime_str(created_at):
    created = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    now = datetime.datetime.utcnow()
    days = (now - created).days
    years = days // 365
    remaining_days = days % 365
    months = remaining_days // 30
    parts = []
    if years:
        parts.append(f"{years} yr{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} mo{'s' if months != 1 else ''}")
    if not parts:
        parts.append(f"{days} days")
    return ", ".join(parts)


def build_sections(user, repos):
    public_repos = user.get("public_repos", 0)
    total_stars = get_total_stars(repos)
    total_commits = get_total_commits(repos)
    followers = user.get("followers", 0)
    top_langs = get_top_languages(repos)

    return [
        ("GitHub", [
            ("Username", USERNAME),
            ("Uptime", uptime_str(user["created_at"])),
            ("Location", "Switzerland"),
        ]),
        ("Contact", [
            ("Website", "egorz.com"),
            ("GitHub", f"github.com/{USERNAME}"),
        ]),
        ("Stats", [
            ("Public Repos", str(public_repos)),
            ("Total Stars", str(total_stars)),
            ("Total Commits", str(total_commits)),
            ("Followers", str(followers)),
        ]),
        ("Top Languages", [(lang, f"{pct:.1f}%") for lang, pct in top_langs]),
    ]


def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# Pixel-positioned SVG, in the spirit of gitascii.com's widget renderers:
# every line gets an explicit x/y instead of relying on a shared monospace
# character grid, so braille art and regular text can never drift apart.
FONT_SIZE = 15
LINE_HEIGHT = 20
CHAR_WIDTH = FONT_SIZE * 0.6
LEFT_PAD = 20
COLUMN_GAP = 90
TOP_PAD = 24
BOTTOM_PAD = 24
FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

BG_COLOR = "#170808"
BORDER_COLOR = "#4a1414"
ART_COLOR = "#ff5f5f"
HEADER_COLOR = "#ff3b3b"
LABEL_COLOR = "#ff8c69"
VALUE_COLOR = "#f2d0c9"
CONNECTOR_COLOR = "#8a4a4a"


def build_svg(ascii_lines, sections):
    right_lines = []  # each item: ("header" | "row", text-or-(label,value))
    for title, rows in sections:
        if right_lines:
            right_lines.append(("gap", ""))
        right_lines.append(("header", title))
        for i, (label, value) in enumerate(rows):
            connector = "└─" if i == len(rows) - 1 else "├─"
            right_lines.append(("row", (connector, label, value)))

    ascii_width = max((len(l) for l in ascii_lines), default=0) * CHAR_WIDTH
    right_x = LEFT_PAD + ascii_width + COLUMN_GAP

    height = TOP_PAD + BOTTOM_PAD + max(len(ascii_lines), len(right_lines)) * LINE_HEIGHT
    width = right_x + 340

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT_FAMILY}">'
    )
    parts.append(
        f'<rect width="{width:.0f}" height="{height:.0f}" rx="12" fill="{BG_COLOR}" '
        f'stroke="{BORDER_COLOR}"/>'
    )

    for i, line in enumerate(ascii_lines):
        y = TOP_PAD + (i + 1) * LINE_HEIGHT
        parts.append(
            f'<text x="{LEFT_PAD}" y="{y:.1f}" font-size="{FONT_SIZE}" '
            f'fill="{ART_COLOR}" xml:space="preserve">{escape_xml(line)}</text>'
        )

    for i, (kind, payload) in enumerate(right_lines):
        y = TOP_PAD + (i + 1) * LINE_HEIGHT
        if kind == "header":
            parts.append(
                f'<text x="{right_x:.1f}" y="{y:.1f}" font-size="{FONT_SIZE}" '
                f'font-weight="700" fill="{HEADER_COLOR}">{escape_xml(payload)}</text>'
            )
        elif kind == "row":
            connector, label, value = payload
            parts.append(
                f'<text x="{right_x:.1f}" y="{y:.1f}" font-size="{FONT_SIZE}" fill="{CONNECTOR_COLOR}">'
                f'{connector} </text>'
                f'<text x="{right_x + 3 * CHAR_WIDTH:.1f}" y="{y:.1f}" font-size="{FONT_SIZE}" '
                f'fill="{LABEL_COLOR}">{escape_xml(label)}</text>'
                f'<text x="{right_x + (3 + len(label) + 1) * CHAR_WIDTH:.1f}" y="{y:.1f}" '
                f'font-size="{FONT_SIZE}" fill="{CONNECTOR_COLOR}"> ➜ </text>'
                f'<text x="{right_x + (3 + len(label) + 5) * CHAR_WIDTH:.1f}" y="{y:.1f}" '
                f'font-size="{FONT_SIZE}" fill="{VALUE_COLOR}">{escape_xml(value)}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    ascii_path = os.path.join(repo_root, "ascii_art.txt")
    readme_path = os.path.join(repo_root, "README.md")
    svg_path = os.path.join(repo_root, "profile-card.svg")

    with open(ascii_path, "r", encoding="utf-8") as f:
        ascii_lines = f.read().splitlines()

    user = get_user()
    repos = get_repos()
    sections = build_sections(user, repos)
    svg = build_svg(ascii_lines, sections)

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    start_marker = "<!--STATS:START-->"
    end_marker = "<!--STATS:END-->"
    start_idx = readme.index(start_marker) + len(start_marker)
    end_idx = readme.index(end_marker)
    # GitHub's CDN and browsers cache raw SVGs by URL. Key the cache-buster
    # off a hash of the SVG's own content (stable, and only ever changes
    # when the image actually changes) and use the absolute
    # raw.githubusercontent.com URL so caching keys off one canonical
    # address instead of a relative path GitHub can resolve differently
    # depending on where it's viewed from.
    cache_bust = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:12]
    block = (
        f'<img src="https://raw.githubusercontent.com/{USERNAME}/{USERNAME}/main/'
        f'profile-card.svg?v={cache_bust}" alt="rs4t GitHub stats" />'
    )
    new_readme = readme[:start_idx] + "\n" + block + "\n" + readme[end_idx:]

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)


if __name__ == "__main__":
    main()
