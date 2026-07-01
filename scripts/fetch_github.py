from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import requests

API = "https://api.github.com"


def fetch(username: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    user = requests.get(f"{API}/users/{username}", headers=headers, timeout=15)
    user.raise_for_status()
    u = user.json()

    repos = requests.get(
        f"{API}/users/{username}/repos",
        headers=headers,
        params={"per_page": 100, "sort": "updated"},
        timeout=15,
    )
    repos.raise_for_status()
    langs = Counter(r["language"] for r in repos.json() if r.get("language") and not r.get("fork"))

    return {
        "login": u.get("login"),
        "name": u.get("name"),
        "email": u.get("email"),
        "bio": u.get("bio"),
        "company": u.get("company"),
        "blog": u.get("blog"),
        "location": u.get("location"),
        "html_url": u.get("html_url"),
        "languages": [name for name, _ in langs.most_common(12)],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/fetch_github.py <username> [inputs_dir]", file=sys.stderr)
        return 2
    username = sys.argv[1]
    inputs_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("real_test")

    data = fetch(username)
    gh_dir = inputs_dir / "github"
    gh_dir.mkdir(parents=True, exist_ok=True)
    (gh_dir / f"{data['login']}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    urls_file = inputs_dir / "github_urls.txt"
    url = data["html_url"] or f"https://github.com/{username}"
    existing = urls_file.read_text(encoding="utf-8").split() if urls_file.exists() else []
    if url not in existing:
        existing.append(url)
    urls_file.write_text("\n".join(existing) + "\n", encoding="utf-8")

    print(f"wrote {gh_dir / (data['login'] + '.json')}")
    print(f"languages: {data['languages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
