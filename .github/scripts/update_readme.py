import os
import re
import time
import requests
from html import escape
from urllib.parse import quote

# =========================================================
# update_readme.py
# - Updates README.md between:
#     <!-- PROJECTS:START -->  ... <!-- PROJECTS:END -->
# - Portfolio behavior:
#     • Top 8 shown as premium cards
#     • Remaining projects in ONE collapsible (same card style)
#     • ML/AI/LLM prioritized (heuristic scoring)
# - No noisy buttons:
#     • Title is clickable
#     • One clean "↗ Open project" link
#     • One line of tags (badges)
# - Cache-bust placeholder: __CACHE_BUST__
# =========================================================

USERNAME = os.environ.get("USERNAME", "").strip()  # e.g. Navyagowda2714
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = "README.md"

if not USERNAME:
    raise SystemExit("USERNAME env var is required (e.g. Navyagowda2714)")

HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# ----------------------------
# GitHub API
# ----------------------------
def fetch_repos():
    """
    Fetch public, non-fork, non-archived repos owned by USERNAME.
    """
    url = f"https://api.github.com/users/{USERNAME}/repos"
    params = {"per_page": 100, "sort": "updated", "direction": "desc", "type": "owner"}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    repos = r.json()

    clean = []
    for repo in repos:
        if repo.get("private") or repo.get("fork") or repo.get("archived"):
            continue
        # skip the profile repo itself
        if repo.get("name", "").lower() == USERNAME.lower():
            continue
        clean.append(repo)
    return clean


# ----------------------------
# Scoring (AI/ML first)
# ----------------------------
KEYWORDS = {
    # LLM / GenAI
    "llm": 20, "rag": 18, "langchain": 18, "embedding": 14, "embeddings": 14,
    "agent": 14, "agents": 14, "genai": 16, "prompt": 12, "transformer": 14, "nlp": 12,
    # ML / DL
    "machine learning": 14, "deep learning": 14, "prediction": 12, "classification": 12,
    "regression": 10, "clustering": 12, "kmeans": 12, "k-means": 12,
    # Computer Vision
    "computer vision": 16, "cnn": 14, "image": 10, "opencv": 10, "segmentation": 12, "vision": 10,
    # Analytics / TS
    "analytics": 10, "time series": 12, "forecast": 12, "financial": 10, "stock": 12,
    # domain boosts
    "health": 10, "medical": 10, "als": 14, "stroke": 14,
}

DEPRIORITIZE = {"test": -4, "demo": -3, "practice": -6, "tmp": -7, "sample": -3, "notes": -3}

def norm(s: str) -> str:
    return " ".join((s or "").lower().replace("_", " ").replace("-", " ").split())

def repo_score(repo: dict) -> float:
    name = norm(repo.get("name", ""))
    desc = norm(repo.get("description", "") or "")
    blob = f"{name} {desc}"

    score = 0.0
    for k, w in KEYWORDS.items():
        if k in blob:
            score += w
    for k, w in DEPRIORITIZE.items():
        if k in blob:
            score += w

    lang = (repo.get("language") or "").lower()
    if lang in {"python", "jupyter notebook"}:
        score += 3.0
    if lang == "swift":
        score += 2.0

    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    score += min(stars * 0.6, 6)
    score += min(forks * 0.3, 3)

    if repo.get("description"):
        score += 1.2

    # tiny freshness bump
    if repo.get("pushed_at"):
        score += 0.5

    return score

def sort_repos(repos: list[dict]) -> list[dict]:
    def key(repo):
        updated = repo.get("pushed_at") or repo.get("updated_at") or ""
        stars = repo.get("stargazers_count", 0) or 0
        return (repo_score(repo), updated, stars)
    return sorted(repos, key=key, reverse=True)


# ----------------------------
# Visual helpers
# ----------------------------
def badge(label: str, value: str, color="111827", logo=None) -> str:
    """
    Small chip badges (one line). Uses single URL-encoding (no Open%20 nonsense).
    """
    lab = quote(label.replace("-", "--"))
    val = quote(value.replace("-", "--"))
    base = f"https://img.shields.io/badge/{lab}-{val}-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<img src="{base}"/>'

def short_desc(desc: str | None) -> str:
    if not desc:
        return "Project repository"
    d = " ".join(desc.split())
    if len(d) > 140:
        d = d[:137].rstrip() + "…"
    return escape(d)

def tags_for(repo: dict) -> list[str]:
    """
    One-line tags. Keep it clean: max 4 chips.
    """
    n = norm(repo.get("name", ""))
    d = norm(repo.get("description", "") or "")
    blob = f"{n} {d}"
    lang = (repo.get("language") or "Project").strip()

    tags = []

    # LLM / GenAI
    if any(k in blob for k in ["llm", "rag", "langchain", "embedding", "embeddings", "agent", "agents", "prompt", "nlp", "transformer", "genai"]):
        tags += [
            badge("GenAI", "LLM", "0EA5E9"),
            badge("RAG", "Pipelines", "7C3AED"),
        ]

    # CV
    if any(k in blob for k in ["computer vision", "cnn", "image", "opencv", "segmentation", "vision"]):
        tags += [
            badge("CV", "Vision", "2563EB"),
            badge("DL", "CNN", "7C3AED"),
        ]

    # ML / Analytics
    if any(k in blob for k in ["machine learning", "deep learning", "clustering", "kmeans", "k-means", "prediction", "regression", "analytics", "forecast", "time series", "stock", "financial"]):
        tags += [
            badge("ML", "Modeling", "16A34A"),
            badge("Analytics", "Insights", "0EA5E9"),
        ]

    # iOS
    if any(k in blob for k in ["swift", "swiftui", "ios", "websocket", "websockets", "real time", "realtime"]):
        tags += [
            badge("Swift", "SwiftUI", "F05138", "swift"),
            badge("Realtime", "WebSockets", "DC2626"),
        ]

    if not tags:
        # fallback to language tag
        tags = [badge("Stack", lang, "111827")]

    # unique, preserve order, max 4
    out, seen = [], set()
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out[:4]


# ----------------------------
# Card + Grid
# ----------------------------
def repo_card(repo: dict) -> str:
    """
    Clean portfolio card:
      - Clickable title
      - One interactive "↗ Open project" link
      - One-line tags
    """
    name = escape(repo["name"])
    url = repo["html_url"]
    desc = short_desc(repo.get("description"))

    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    updated_at = repo.get("pushed_at") or repo.get("updated_at") or ""
    updated_short = updated_at[:10] if updated_at else ""

    tag_line = " ".join(tags_for(repo))

    # Interactive text link (no badges, no encoding ugliness)
    open_link = f'<a href="{url}"><b>↗ Open project</b></a>'

    return (
        '<td width="50%" valign="top">\n'
        "<div>\n"
        f'  <h3>⭐ <a href="{url}">{name}</a></h3>\n'
        f"  <p>{desc}</p>\n"
        f"  <sub>⭐ {stars} &nbsp;•&nbsp; 🍴 {forks} &nbsp;•&nbsp; 🕒 {escape(updated_short)}</sub>\n"
        "  <br/><br/>\n"
        f"  {open_link}\n"
        "  <br/><br/>\n"
        f"  {tag_line}\n"
        "</div>\n"
        "</td>"
    )

def build_table(repos: list[dict]) -> str:
    rows = []
    for i in range(0, len(repos), 2):
        left = repo_card(repos[i])
        right = repo_card(repos[i + 1]) if i + 1 < len(repos) else '<td width="50%"></td>'
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"

def build_projects_block(repos_sorted: list[dict], top_n=8) -> str:
    """
    Top 8 shown. Rest in ONE collapsible, same exact card grid.
    No category sections. No messy extra headings.
    """
    top = repos_sorted[:top_n]
    rest = repos_sorted[top_n:]

    top_table = build_table(top) if top else "<sub>No public projects found.</sub>"

    if not rest:
        return top_table

    rest_table = build_table(rest)

    # IMPORTANT: no indentation inside details to avoid GitHub rendering it as code
    collapsible = (
        f"<details>\n"
        f"<summary><b>📚 View all projects ({len(rest)} more)</b></summary>\n"
        f"<br/>\n"
        f"{rest_table}\n"
        f"</details>"
    )

    return f"{top_table}\n\n{collapsible}"


# ----------------------------
# README editing
# ----------------------------
def replace_between_markers(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(rf"({re.escape(start)})(.*?)(\s*{re.escape(end)})", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers not found: {start} ... {end}")
    return pattern.sub(rf"\1\n{replacement}\n\3", text, count=1)

def bump_cache_bust(text: str) -> str:
    return text.replace("__CACHE_BUST__", str(int(time.time())))

def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    repos = fetch_repos()
    repos_sorted = sort_repos(repos)

    projects_html = build_projects_block(repos_sorted, top_n=8)

    readme = replace_between_markers(
        readme,
        "<!-- PROJECTS:START -->",
        "<!-- PROJECTS:END -->",
        projects_html,
    )

    readme = bump_cache_bust(readme)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    main()
