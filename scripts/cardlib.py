"""Shared logic for building the rs4t profile card SVG.

Used both by scripts/update_readme.py (writes a static, self-animating
fallback SVG into the repo via GitHub Actions) and scripts/server.py
(serves a single frame per request, picked from the real wall clock, for
the home-server-hosted dynamic version).
"""
import os
import datetime
import urllib.request
import json

USERNAME = "rs4t"
API = "https://api.github.com"
ART_CYCLE_SECONDS = 30

# Pixel-positioned SVG: every line gets an explicit x/y instead of relying
# on a shared monospace character grid, so braille art and regular text
# can never drift apart.
FONT_SIZE = 15
LINE_HEIGHT = 20
CHAR_WIDTH = FONT_SIZE * 0.6
LEFT_PAD = 20
COLUMN_GAP = 150
RIGHT_PAD = 20
TOP_PAD = 24
BOTTOM_PAD = 24
FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

BG_COLOR = "#0d1117"
BORDER_COLOR = "#30363d"
ART_COLOR = "#ff5f5f"
HEADER_COLOR = "#ff3b3b"
LABEL_COLOR = "#ff8c69"
VALUE_COLOR = "#f2d0c9"
CONNECTOR_COLOR = "#c05656"
PROMPT_COLOR = "#8a4a4a"

PROMPT_TEXT = f"{USERNAME}@github:~$ gitfetch"
CONTENT_TOP = TOP_PAD + LINE_HEIGHT + 10


def make_headers(token):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_get(path, headers, params=None):
    url = f"{API}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode()), dict(resp.headers)


def paginate(path, headers, params=None):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    items = []
    while True:
        params["page"] = page
        data, _ = api_get(path, headers, params)
        if not data:
            break
        items.extend(data)
        if len(data) < params["per_page"]:
            break
        page += 1
    return items


def get_user(headers):
    data, _ = api_get(f"/users/{USERNAME}", headers)
    return data


def get_repos(headers):
    return paginate(f"/users/{USERNAME}/repos", headers, {"type": "owner"})


def get_total_stars(repos):
    return sum(r.get("stargazers_count", 0) for r in repos)


def get_total_commits(repos, headers):
    total = 0
    for r in repos:
        if r.get("fork"):
            continue
        full_name = r["full_name"]
        try:
            _, resp_headers = api_get(
                f"/repos/{full_name}/commits",
                headers,
                {"author": USERNAME, "per_page": 1},
            )
            link = resp_headers.get("Link", "")
            if 'rel="last"' in link:
                last_part = [p for p in link.split(",") if 'rel="last"' in p][0]
                page_str = last_part.split("page=")[-1].split(">")[0].split("&")[0]
                total += int(page_str)
            else:
                data, _ = api_get(
                    f"/repos/{full_name}/commits",
                    headers,
                    {"author": USERNAME, "per_page": 100},
                )
                total += len(data)
        except Exception:
            continue
    return total


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


def build_sections(user, repos, headers):
    public_repos = user.get("public_repos", 0)
    total_stars = get_total_stars(repos)
    total_commits = get_total_commits(repos, headers)
    followers = user.get("followers", 0)

    return [
        ("GitHub", [
            ("Username", USERNAME),
            ("Uptime", uptime_str(user["created_at"])),
            ("Location", "Switzerland"),
        ]),
        ("Contact", [
            ("Website", "zegg.me"),
            ("GitHub", f"github.com/{USERNAME}"),
        ]),
        ("Stats", [
            ("Public Repos", str(public_repos)),
            ("Total Stars", str(total_stars)),
            ("Total Commits", str(total_commits)),
            ("Followers", str(followers)),
        ]),
    ]


def load_ascii_art_sets(repo_root):
    path = os.path.join(repo_root, "ascii_arts.txt")
    with open(path, "r", encoding="utf-8") as f:
        raw_arts = f.read().split("\n===\n")
    return [art.splitlines() for art in raw_arts if art.strip()]


def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _right_lines_from_sections(sections):
    right_lines = []  # each item: ("header" | "row", text-or-(label,value))
    for title, rows in sections:
        if right_lines:
            right_lines.append(("gap", ""))
        right_lines.append(("header", title))
        for i, (label, value) in enumerate(rows):
            connector = "└─" if i == len(rows) - 1 else "├─"
            right_lines.append(("row", (connector, label, value)))
    return right_lines


def _line_width(kind, payload):
    if kind == "header":
        return len(payload)
    connector, label, value = payload
    # connector(2) + space + label + " ➜ " + value, in character cells
    return 2 + 1 + len(label) + 3 + len(value)


def _prompt_text(width):
    y = TOP_PAD + LINE_HEIGHT * 0.75
    return [
        f'<text x="{LEFT_PAD}" y="{y:.1f}" font-size="{FONT_SIZE}" '
        f'fill="{PROMPT_COLOR}" xml:space="preserve">{escape_xml(PROMPT_TEXT)}</text>',
        f'<line x1="{LEFT_PAD}" y1="{CONTENT_TOP - LINE_HEIGHT * 0.35:.1f}" '
        f'x2="{width - RIGHT_PAD:.1f}" y2="{CONTENT_TOP - LINE_HEIGHT * 0.35:.1f}" '
        f'stroke="{BORDER_COLOR}"/>',
    ]


def _art_text(ascii_lines):
    parts = []
    for i, line in enumerate(ascii_lines):
        y = CONTENT_TOP + (i + 1) * LINE_HEIGHT
        parts.append(
            f'<text x="{LEFT_PAD}" y="{y:.1f}" font-size="{FONT_SIZE}" '
            f'fill="{ART_COLOR}" xml:space="preserve">{escape_xml(line)}</text>'
        )
    return parts


def _stats_text(right_lines, right_x):
    parts = []
    for i, (kind, payload) in enumerate(right_lines):
        y = CONTENT_TOP + (i + 1) * LINE_HEIGHT
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
    return parts


def _svg_frame(width, height, body_parts):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT_FAMILY}">',
        f'<rect width="{width:.0f}" height="{height:.0f}" rx="12" fill="{BG_COLOR}" '
        f'stroke="{BORDER_COLOR}"/>',
    ]
    parts.extend(body_parts)
    parts.append("</svg>")
    return "\n".join(parts)


def build_svg_animated(ascii_art_sets, sections):
    """All arts layered and cross-faded with client-side SMIL animation.

    Used for the static repo-hosted fallback: it can't sync to wall clock
    (each page load resets the animation timer to 0), but it degrades
    gracefully as a plain file with no server behind it.
    """
    right_lines = _right_lines_from_sections(sections)
    ascii_width = max(
        (len(line) for art in ascii_art_sets for line in art), default=0
    ) * CHAR_WIDTH
    right_x = LEFT_PAD + ascii_width + COLUMN_GAP
    max_right_chars = max(
        (_line_width(kind, payload) for kind, payload in right_lines if kind != "gap"),
        default=0,
    )
    max_art_lines = max((len(art) for art in ascii_art_sets), default=0)
    height = CONTENT_TOP + BOTTOM_PAD + max(max_art_lines, len(right_lines)) * LINE_HEIGHT
    width = right_x + max_right_chars * CHAR_WIDTH + RIGHT_PAD

    body = _prompt_text(width)
    art_count = len(ascii_art_sets)
    total_dur = ART_CYCLE_SECONDS * art_count
    for art_index, ascii_lines in enumerate(ascii_art_sets):
        values = ["1" if k == art_index else "0" for k in range(art_count)] + ["0"]
        key_times = [k / art_count for k in range(art_count + 1)]
        body.append(f'<g opacity="{values[0]}">')
        body.extend(_art_text(ascii_lines))
        if art_count > 1:
            body.append(
                '<animate attributeName="opacity" calcMode="discrete" '
                f'begin="0s" dur="{total_dur}s" repeatCount="indefinite" '
                f'keyTimes="{";".join(f"{t:.4f}" for t in key_times)}" '
                f'values="{";".join(values)}"/>'
            )
        body.append("</g>")
    body.extend(_stats_text(right_lines, right_x))
    return _svg_frame(width, height, body)


def build_svg_frame(ascii_art_sets, sections, art_index):
    """A single, static frame for the given art index (no animation).

    Used by the home-server endpoint: the index is picked per-request from
    the real wall clock, so every viewer at the same moment gets the same
    art without needing any client-side animation at all.
    """
    ascii_lines = ascii_art_sets[art_index % len(ascii_art_sets)]
    right_lines = _right_lines_from_sections(sections)
    ascii_width = max(
        (len(line) for art in ascii_art_sets for line in art), default=0
    ) * CHAR_WIDTH
    right_x = LEFT_PAD + ascii_width + COLUMN_GAP
    max_right_chars = max(
        (_line_width(kind, payload) for kind, payload in right_lines if kind != "gap"),
        default=0,
    )
    max_art_lines = max((len(art) for art in ascii_art_sets), default=0)
    height = CONTENT_TOP + BOTTOM_PAD + max(max_art_lines, len(right_lines)) * LINE_HEIGHT
    width = right_x + max_right_chars * CHAR_WIDTH + RIGHT_PAD

    body = _prompt_text(width) + _art_text(ascii_lines) + _stats_text(right_lines, right_x)
    return _svg_frame(width, height, body)


def current_art_index(art_count):
    import time
    return (int(time.time()) // ART_CYCLE_SECONDS) % art_count
