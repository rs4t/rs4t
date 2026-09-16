#!/usr/bin/env python3
"""Regenerate the repo-hosted fallback profile-card.svg and README.md.

The live, wall-clock-synced card is served by scripts/server.py on the
home server; this script just keeps a static, self-animating copy in the
repo as a backup for whenever that server is unreachable.
"""
import os

import cardlib

CARD_URL = "https://card.zegg.me/profile-card.svg"


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    readme_path = os.path.join(repo_root, "README.md")
    svg_path = os.path.join(repo_root, "profile-card.svg")

    ascii_art_sets = cardlib.load_ascii_art_sets(repo_root)

    headers = cardlib.make_headers(os.environ.get("GITHUB_TOKEN"))
    user = cardlib.get_user(headers)
    repos = cardlib.get_repos(headers)
    sections = cardlib.build_sections(user, repos, headers)
    svg = cardlib.build_svg_animated(ascii_art_sets, sections)

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    start_marker = "<!--STATS:START-->"
    end_marker = "<!--STATS:END-->"
    start_idx = readme.index(start_marker) + len(start_marker)
    end_idx = readme.index(end_marker)
    # Primary: the home server, which picks the current art from the real
    # wall clock so every viewer at a given moment sees the same one.
    # Fallback: stale-if-error on the server's own Cache-Control means a
    # browser that fetched it before an outage keeps showing the last good
    # copy; this repo-hosted animated SVG is the last-resort manual
    # fallback if the server is retired or down for good.
    block = f'<img src="{CARD_URL}" alt="rs4t GitHub stats" width="100%" />'
    new_readme = readme[:start_idx] + "\n" + block + "\n" + readme[end_idx:]

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)


if __name__ == "__main__":
    main()
