#!/usr/bin/env python3
"""Fetch GitHub stats for rs4t and rewrite the neofetch-style block in README.md."""
import os
import sys
import datetime
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


def build_section(title, rows):
    lines = [title]
    for i, (label, value) in enumerate(rows):
        connector = "└─" if i == len(rows) - 1 else "├─"
        lines.append(f"{connector} {label} ➜ {value}")
    return lines


def build_stats_lines():
    user = get_user()
    repos = get_repos()

    public_repos = user.get("public_repos", 0)
    total_stars = get_total_stars(repos)
    total_commits = get_total_commits(repos)
    followers = user.get("followers", 0)
    top_langs = get_top_languages(repos)

    github_section = build_section("GitHub", [
        ("Username", USERNAME),
        ("Uptime", uptime_str(user["created_at"])),
        ("Location", "Switzerland"),
    ])
    contact_section = build_section("Contact", [
        ("Website", "egorz.com"),
        ("GitHub", f"github.com/{USERNAME}"),
    ])
    stats_section = build_section("Stats", [
        ("Public Repos", str(public_repos)),
        ("Total Stars", str(total_stars)),
        ("Total Commits", str(total_commits)),
        ("Followers", str(followers)),
    ])
    lang_rows = [(lang, f"{pct:.1f}%") for lang, pct in top_langs]
    lang_section = build_section("Top Languages", lang_rows)

    right = []
    for section in (github_section, contact_section, stats_section, lang_section):
        right.extend(section)
        right.append("")
    while right and right[-1] == "":
        right.pop()
    return right


def combine(ascii_lines, right_lines):
    width = max((len(l) for l in ascii_lines), default=0)
    height = max(len(ascii_lines), len(right_lines))
    out = []
    for i in range(height):
        left = ascii_lines[i] if i < len(ascii_lines) else ""
        right = right_lines[i] if i < len(right_lines) else ""
        out.append(f"{left.ljust(width)}   {right}".rstrip())
    return out


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    ascii_path = os.path.join(repo_root, "ascii_art.txt")
    readme_path = os.path.join(repo_root, "README.md")

    with open(ascii_path, "r", encoding="utf-8") as f:
        ascii_lines = f.read().splitlines()

    right_lines = build_stats_lines()
    combined = combine(ascii_lines, right_lines)

    block = "```text\n" + "\n".join(combined) + "\n```"

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    start_marker = "<!--STATS:START-->"
    end_marker = "<!--STATS:END-->"
    start_idx = readme.index(start_marker) + len(start_marker)
    end_idx = readme.index(end_marker)
    new_readme = readme[:start_idx] + "\n" + block + "\n" + readme[end_idx:]

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)


if __name__ == "__main__":
    main()
