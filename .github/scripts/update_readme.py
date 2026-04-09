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
# - Card alignment fix:
#     • Clamp description aggressively
#     • Keep consistent "slots" per card
#     • Add spacer padding so table rows align better in GitHub
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

TOP_N = 8
DESC_MAX = 90  # tighter clamp => more equal heights across cards


# ----------------------------
# GitHub API
# ----------------------------
def norm(s: str) -> str:
    return " ".join((s or "").lower().replace("_", " ").replace("-", " ").split())


def should_exclude_repo(repo: dict) -> bool:
    """
    Exclude non-project repos such as profile/portfolio/meta repos.
    Keep this conservative so only clearly unsuitable repos are removed.
    """
    raw_name = repo.get("name", "") or ""
    raw_desc = repo.get("description", "") or ""

    name = norm(raw_name)
    desc = norm(raw_desc)
    blob = f"{name} {desc}"

    username_norm = norm(USERNAME)
    username_alpha = re.sub(r"\d+", "", username_norm).strip()

    # Exact username repo (GitHub profile README repo or equivalent)
    if raw_name.lower() == USERNAME.lower():
        return True

    # Ignore obvious personal profile / portfolio repos
    exclude_phrases = [
        "personal github profile",
        "github profile",
        "profile repository",
        "portfolio repository",
        "personal portfolio",
        "my portfolio",
        "profile readme",
    ]
    if any(p in blob for p in exclude_phrases):
        return True

    # Common profile/portfolio repo naming patterns
    if username_norm and name == username_norm:
        return True
    if username_alpha and name == username_alpha:
        return True
    if username_alpha and username_alpha in name and any(k in blob for k in ["profile", "portfolio", "readme"]):
        return True

    return False


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
        if should_exclude_repo(repo):
            continue
        clean.append(repo)
    return clean


# ----------------------------
# Scoring (AI/ML first)
# ----------------------------
KEYWORDS = {
    # LLM / GenAI
    "llm": 24,
    "rag": 22,
    "langchain": 20,
    "embedding": 16,
    "embeddings": 16,
    "agent": 16,
    "agents": 16,
    "genai": 18,
    "prompt": 14,
    "transformer": 16,
    "nlp": 14,

    # ML / DL / MLOps
    "machine learning": 18,
    "deep learning": 18,
    "prediction": 14,
    "classification": 14,
    "regression": 12,
    "clustering": 12,
    "kmeans": 12,
    "k-means": 12,
    "mlops": 20,
    "pipeline": 16,
    "pipelines": 16,
    "training": 10,
    "inference": 10,

    # Computer Vision
    "computer vision": 16,
    "cnn": 14,
    "image": 10,
    "opencv": 10,
    "segmentation": 12,
    "vision": 10,

    # Analytics / TS / Data
    "analytics": 12,
    "time series": 14,
    "forecast": 12,
    "financial": 10,
    "stock": 14,
    "big data": 14,
    "data science": 14,
    "data analysis": 12,
    "dataset": 10,

    # domain boosts
    "health": 10,
    "medical": 10,
    "als": 16,
    "stroke": 18,
    "wheat": 14,
    "university": 8,
    "learning analytics": 16,
}

DEPRIORITIZE = {
    "test": -4,
    "demo": -3,
    "practice": -6,
    "tmp": -7,
    "sample": -3,
    "notes": -3,
    "portfolio": -40,
    "profile": -50,
    "readme": -10,
}

STRONG_PROJECT_NAME_BOOSTS = {
    "stroke": 10,
    "mlops": 12,
    "stock": 8,
    "wheat": 8,
    "analytics": 8,
    "prediction": 8,
    "classification": 8,
}


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

    # Prefer real project-style repos with technical naming
    for k, w in STRONG_PROJECT_NAME_BOOSTS.items():
        if k in name:
            score += w

    # Slight boost for richer descriptions
    if repo.get("description"):
        score += 1.5

    # Language preference
    lang = (repo.get("language") or "").lower()
    if lang in {"python", "jupyter notebook"}:
        score += 5.0
    elif lang in {"swift"}:
        score += 2.0
    elif lang in {"r", "scala"}:
        score += 2.0

    # Social proof
    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    score += min(stars * 0.6, 6)
    score += min(forks * 0.3, 3)

    # Freshness bump
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
    Small chip badges (one line).
    """
    lab = quote(label.replace("-", "--"))
    val = quote(value.replace("-", "--"))
    base = f"https://img.shields.io/badge/{lab}-{val}-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<img src="{base}"/>'


def short_desc(desc: str | None) -> str:
    """
    Clamp aggressively to keep cards aligned.
    """
    if not desc:
        return "Project repository"
    d = " ".join(desc.split())
    if len(d) > DESC_MAX:
        d = d[:DESC_MAX - 1].rstrip() + "…"
    return escape(d)


def tags_for(repo: dict) -> list[str]:
    """
    One-line tags. Max 4 chips.
    """
    n = norm(repo.get("name", ""))
    d = norm(repo.get("description", "") or "")
    blob = f"{n} {d}"
    lang = (repo.get("language") or "Project").strip()

    tags = []

    if any(k in blob for k in ["llm", "rag", "langchain", "embedding", "embeddings", "agent", "agents", "prompt", "nlp", "transformer", "genai"]):
        tags += [
            badge("GenAI", "LLM", "0EA5E9"),
            badge("RAG", "Pipelines", "7C3AED"),
        ]

    if any(k in blob for k in ["computer vision", "cnn", "image", "opencv", "segmentation", "vision"]):
        tags += [
            badge("CV", "Vision", "2563EB"),
            badge("DL", "CNN", "7C3AED"),
        ]

    if any(k in blob for k in ["machine learning", "deep learning", "clustering", "kmeans", "k-means", "prediction", "regression", "analytics", "forecast", "time series", "stock", "financial", "dataset", "data science", "data analysis"]):
        tags += [
            badge("ML", "Modeling", "16A34A"),
            badge("Analytics", "Insights", "0EA5E9"),
        ]

    if any(k in blob for k in ["mlops", "pipeline", "pipelines", "deployment", "inference", "training"]):
        tags += [
            badge("MLOps", "Pipelines", "7C3AED"),
        ]

    if any(k in blob for k in ["swift", "swiftui", "ios", "websocket", "websockets", "real time", "realtime"]):
        tags += [
            badge("Swift", "SwiftUI", "F05138", "swift"),
            badge("Realtime", "WebSockets", "DC2626"),
        ]

    if not tags:
        tags = [badge("Stack", lang, "111827")]

    # unique, preserve order, max 4
    out, seen = [], set()
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out[:4]


# ----------------------------
# Card + Grid (alignment-friendly)
# ----------------------------
def repo_card(repo: dict) -> str:
    """
    Alignment strategy:
      - fixed "slots" in same order
      - clamped description
      - spacer lines to normalize heights
    """
    name = escape(repo["name"])
    url = repo["html_url"]
    desc = short_desc(repo.get("description"))

    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    updated_at = repo.get("pushed_at") or repo.get("updated_at") or ""
    updated_short = updated_at[:10] if updated_at else ""

    tag_line = " ".join(tags_for(repo))
    open_link = f'<a href="{url}"><b>↗ Open project</b></a>'

    # Two spacer lines after description to keep link row aligned across different desc lengths
    # (GitHub tables don’t equalize height, this helps a lot)
    return (
        '<td width="50%" valign="top">\n'
        "<div>\n"
        f'  <h3>⭐ <a href="{url}">{name}</a></h3>\n'
        f"  <p>{desc}</p>\n"
        "  <br/>\n"
        "  <br/>\n"
        f"  <sub>⭐ {stars} &nbsp;•&nbsp; 🍴 {forks} &nbsp;•&nbsp; 🕒 {escape(updated_short)}</sub>\n"
        "  <br/><br/>\n"
        f"  {open_link}\n"
        "  <br/><br/>\n"
        f"  {tag_line}\n"
        "</div>\n"
        "</td>"
    )


def blank_card() -> str:
    """
    Keep table geometry stable when odd number of cards.
    """
    return (
        '<td width="50%" valign="top">\n'
        "<div>\n"
        "  <h3>&nbsp;</h3>\n"
        "  <p>&nbsp;</p>\n"
        "  <br/>\n"
        "  <br/>\n"
        "  <sub>&nbsp;</sub>\n"
        "  <br/><br/>\n"
        "  <br/>\n"
        "  <br/><br/>\n"
        "  &nbsp;\n"
        "</div>\n"
        "</td>"
    )


def build_table(repos: list[dict]) -> str:
    rows = []
    for i in range(0, len(repos), 2):
        left = repo_card(repos[i])
        right = repo_card(repos[i + 1]) if i + 1 < len(repos) else blank_card()
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def build_projects_block(repos_sorted: list[dict], top_n=TOP_N) -> str:
    top = repos_sorted[:top_n]
    rest = repos_sorted[top_n:]

    top_table = build_table(top) if top else "<sub>No public projects found.</sub>"

    if not rest:
        return top_table

    rest_table = build_table(rest)

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

    projects_html = build_projects_block(repos_sorted, top_n=TOP_N)

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
