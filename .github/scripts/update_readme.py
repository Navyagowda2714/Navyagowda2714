import os
import re
import time
import requests
from html import escape
from urllib.parse import quote

# =========================================================
#  update_readme.py
#  - Builds a portfolio-style "Featured Projects" section:
#      • Top 8 shown as premium cards
#      • Remaining projects inside <details> (same card style)
#      • Sorted with ML/AI/LLM projects prioritized
#      • Adds a clear CTA button: "Open Project"
#  - Cache-bust placeholder: __CACHE_BUST__
#
#  REQUIRED in README.md:
#    <!-- PROJECTS:START -->
#    ... (auto generated)
#    <!-- PROJECTS:END -->
# =========================================================

USERNAME = os.environ.get("USERNAME", "").strip()  # e.g. Navyagowda2714
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = "README.md"

if not USERNAME:
    raise SystemExit("USERNAME env var is required (e.g. Navyagowda2714)")

headers = {"Accept": "application/vnd.github+json"}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"


# ----------------------------
# GitHub API
# ----------------------------
def fetch_repos():
    """
    Fetch public, non-fork, non-archived repos owned by USERNAME.
    """
    url = f"https://api.github.com/users/{USERNAME}/repos"
    params = {"per_page": 100, "sort": "updated", "direction": "desc", "type": "owner"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    repos = r.json()

    clean = []
    for repo in repos:
        if repo.get("private") or repo.get("fork") or repo.get("archived"):
            continue
        # Skip the profile repo itself
        if repo.get("name", "").lower() == USERNAME.lower():
            continue
        clean.append(repo)
    return clean


# ----------------------------
# Scoring + Categorization
# ----------------------------
ML_AI_KEYWORDS = {
    # LLM / GenAI
    "llm": 14, "rag": 12, "langchain": 12, "embedding": 10, "embeddings": 10,
    "agent": 10, "agents": 10, "genai": 12, "prompt": 9, "transformer": 10, "nlp": 9,
    # ML / DL
    "machine learning": 10, "deep learning": 10, "model": 5, "prediction": 8,
    "classification": 8, "regression": 7, "clustering": 9, "kmeans": 9, "k-means": 9,
    # CV
    "computer vision": 11, "vision": 9, "cnn": 10, "image": 8, "segmentation": 9, "opencv": 8,
    # Analytics / Time series
    "analytics": 7, "time series": 9, "forecast": 9, "financial": 7, "stock": 8,
    # Domain boosts
    "health": 7, "medical": 7, "als": 10, "stroke": 10,
}

DEPRIORITIZE = {"test": -2, "demo": -2, "practice": -3, "tmp": -4, "sample": -2, "notes": -2}


def normalize_text(s: str) -> str:
    return " ".join((s or "").lower().replace("_", " ").replace("-", " ").split())


def repo_score(repo: dict) -> float:
    name = normalize_text(repo.get("name", ""))
    desc = normalize_text(repo.get("description", ""))
    blob = f"{name} {desc}"

    score = 0.0
    for k, w in ML_AI_KEYWORDS.items():
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

    # weak freshness bump
    if repo.get("pushed_at"):
        score += 0.5

    return score


def sort_repos(repos: list[dict]) -> list[dict]:
    def key(repo):
        score = repo_score(repo)
        updated = repo.get("pushed_at") or repo.get("updated_at") or ""
        stars = repo.get("stargazers_count", 0) or 0
        return (score, updated, stars)

    return sorted(repos, key=key, reverse=True)


def category_of(repo: dict) -> str:
    """
    Bucket into portfolio categories.
    """
    name = normalize_text(repo.get("name", ""))
    desc = normalize_text(repo.get("description", "") or "")
    blob = f"{name} {desc}"

    if any(k in blob for k in ["swift", "swiftui", "ios", "xcode"]):
        return "iOS / Swift"

    if any(k in blob for k in ["llm", "rag", "langchain", "embedding", "embeddings", "prompt", "agent", "agents", "nlp", "transformer"]):
        return "LLM / GenAI"

    if any(k in blob for k in ["computer vision", "cnn", "image", "opencv", "segmentation", "vision"]):
        return "Computer Vision"

    if any(k in blob for k in ["machine learning", "deep learning", "clustering", "kmeans", "k-means", "prediction", "regression", "analytics", "forecast", "time series", "stock", "financial"]):
        return "ML / Analytics"

    return "Other"


# ----------------------------
# Visual helpers (GitHub-safe)
# ----------------------------
def badge(label, value, color="111827", logo=None):
    label = label.replace("-", "--").replace(" ", "%20")
    value = value.replace("-", "--").replace(" ", "%20")
    base = f"https://img.shields.io/badge/{label}-{value}-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<img src="{base}"/>'


def button(label, url, color="1E40AF", logo=None):
    """
    Button look using shields. Safe: no nested f-strings.
    """
    label_text = quote(label.replace(" ", "%20"))
    base = f"https://img.shields.io/badge/{label_text}-Open-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<a href="{url}"><img src="{base}"/></a>'


def short_desc(desc: str | None) -> str:
    if not desc:
        return "Project repository"
    d = " ".join(desc.split())
    if len(d) > 135:
        d = d[:132].rstrip() + "…"
    return escape(d)


def tags_for(repo: dict):
    n = normalize_text(repo.get("name", ""))
    d = normalize_text(repo.get("description", "") or "")
    blob = f"{n} {d}"
    lang = (repo.get("language") or "Project").strip()

    tags = []

    # LLM / GenAI
    if any(k in blob for k in ["llm", "rag", "langchain", "embeddings", "embedding", "agent", "agents", "nlp", "transformer", "genai"]):
        tags += [badge("GenAI", "LLM", "0EA5E9"), badge("RAG", "Pipelines", "7C3AED")]

    # CV
    if any(k in blob for k in ["computer vision", "cnn", "image", "opencv", "segmentation", "vision"]):
        tags += [badge("ComputerVision", "Image", "2563EB"), badge("DeepLearning", "CNN", "7C3AED")]

    # ML / Analytics
    if any(k in blob for k in ["clustering", "kmeans", "k-means", "prediction", "regression", "analytics", "forecast", "time series", "stock", "financial"]):
        tags += [badge("ML", "Modeling", "16A34A"), badge("Analytics", "Insights", "0EA5E9")]

    # iOS
    if any(k in blob for k in ["swift", "swiftui", "ios", "websocket", "real time", "realtime"]):
        tags += [badge("Swift", "SwiftUI", "F05138", "swift"), badge("Realtime", "WebSockets", "DC2626")]

    if not tags:
        tags = [badge("Stack", lang, "111827")]

    # unique, max 3
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out[:3]


# ----------------------------
# Card + Table builders
# ----------------------------
def repo_card(repo: dict) -> str:
    """
    Premium card style (GitHub-safe HTML).
    Adds an interactive CTA button: "Open Project".
    """
    name = escape(repo["name"])
    url = repo["html_url"]
    desc = short_desc(repo.get("description"))
    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    updated_at = repo.get("pushed_at") or repo.get("updated_at") or ""
    updated_short = updated_at[:10] if updated_at else ""

    tag_line = " ".join(tags_for(repo))

    open_btn = button("Open Project", url, "F59E0B", "github")  # CTA
    repo_btn = button("Repo", url, "1E40AF", "github")
    stars_btn = button(f"Stars {stars}", f"{url}/stargazers", "16A34A", "github")

    return (
        "<td width=\"50%\" valign=\"top\">\n"
        "<div>\n"
        f"  <h3>⭐ {name}</h3>\n"
        f"  <p>{desc}</p>\n"
        f"  <sub>⭐ {stars} &nbsp;•&nbsp; 🍴 {forks} &nbsp;•&nbsp; 🕒 {escape(updated_short)}</sub>\n"
        "  <br/><br/>\n"
        f"  {open_btn}\n"
        "  <br/><br/>\n"
        f"  {repo_btn} &nbsp; {stars_btn}\n"
        "  <br/><br/>\n"
        f"  {tag_line}\n"
        "</div>\n"
        "</td>"
    )


def build_table(repos: list[dict]) -> str:
    rows = []
    for i in range(0, len(repos), 2):
        left = repo_card(repos[i])
        right = repo_card(repos[i + 1]) if i + 1 < len(repos) else "<td width=\"50%\"></td>"
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def anchor_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def build_portfolio_projects_block(repos_sorted: list[dict], top_n=8) -> str:
    top = repos_sorted[:top_n]
    rest = repos_sorted[top_n:]

    cats = ["LLM / GenAI", "Computer Vision", "ML / Analytics", "iOS / Swift", "Other"]
    chips = " &nbsp; ".join([f'<a href="#{anchor_id(c)}">{badge("Category", c, "111827")}</a>' for c in cats])

    top_table = build_table(top) if top else "<sub>No public projects found.</sub>"

    if not rest:
        return f"{chips}\n\n{top_table}"

    buckets = {c: [] for c in cats}
    for r in rest:
        buckets[category_of(r)].append(r)

    grouped_parts = []
    for c in cats:
        items = buckets.get(c, [])
        if not items:
            continue
        grouped_parts.append(f'<h3 id="{anchor_id(c)}">📌 {escape(c)}</h3>')
        grouped_parts.append(build_table(items))
        grouped_parts.append("<br/>")

    grouped_html = "\n".join(grouped_parts).strip()

    # IMPORTANT: no leading spaces inside <details> to avoid GitHub rendering as code
    collapsible = (
        f"<details>\n"
        f"<summary><b>📚 View all projects ({len(rest)} more)</b></summary>\n"
        f"<br/>\n"
        f"{grouped_html}\n"
        f"</details>"
    )

    return f"{chips}\n\n{top_table}\n\n{collapsible}"


# ----------------------------
# README editing
# ----------------------------
def replace_between_markers(text, start, end, replacement):
    pattern = re.compile(rf"({re.escape(start)})(.*?)(\s*{re.escape(end)})", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers not found: {start} ... {end}")
    return pattern.sub(rf"\1\n{replacement}\n\3", text, count=1)


def bump_cache_bust(text):
    return text.replace("__CACHE_BUST__", str(int(time.time())))


def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    repos = fetch_repos()
    repos_sorted = sort_repos(repos)

    projects_html = build_portfolio_projects_block(repos_sorted, top_n=8)

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
