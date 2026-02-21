import os
import re
import time
import requests
from html import escape
from urllib.parse import quote

USERNAME = os.environ.get("USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = "README.md"

if not USERNAME:
    raise SystemExit("USERNAME env var is required")

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
        if repo.get("name", "").lower() == USERNAME.lower():
            continue  # profile repo
        clean.append(repo)
    return clean


# ----------------------------
# Scoring + Categorization
# ----------------------------
ML_AI_KEYWORDS = {
    "llm": 12, "rag": 10, "langchain": 10, "embeddings": 9, "agent": 9, "agents": 9,
    "genai": 10, "prompt": 7, "transformer": 8, "nlp": 7,
    "machine learning": 9, "deep learning": 9, "model": 4, "prediction": 6,
    "classification": 6, "regression": 5, "clustering": 7, "kmeans": 7, "k-means": 7,
    "computer vision": 9, "vision": 7, "cnn": 8, "image": 6, "segmentation": 7,
    "analytics": 5, "data": 3, "time series": 6, "forecast": 6,
    "health": 5, "medical": 5, "als": 7, "stroke": 7,
}

DEPRIORITIZE = {
    "test": -2, "demo": -2, "practice": -2, "tmp": -3, "sample": -2, "notes": -2
}

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
        score += 2.5
    if lang == "swift":
        score += 1.5

    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    score += min(stars * 0.6, 6)
    score += min(forks * 0.3, 3)

    if repo.get("description"):
        score += 1.5

    # Freshness signal (weak): pushed recently helps, but relevance matters more
    pushed = repo.get("pushed_at") or ""
    if pushed:
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
    Bucket into portfolio-style categories.
    """
    name = normalize_text(repo.get("name", ""))
    desc = normalize_text(repo.get("description", ""))
    blob = f"{name} {desc}"

    # iOS
    if any(k in blob for k in ["swift", "swiftui", "ios", "xcode", "websocket chat", "socket"]):
        return "iOS / Swift"

    # LLM / GenAI / NLP
    if any(k in blob for k in ["llm", "rag", "langchain", "embeddings", "prompt", "agent", "agents", "nlp", "transformer"]):
        return "LLM / GenAI"

    # CV
    if any(k in blob for k in ["computer vision", "cnn", "image", "segmentation", "classification", "opencv", "vision"]):
        return "Computer Vision"

    # ML / Analytics (general)
    if any(k in blob for k in ["machine learning", "deep learning", "clustering", "kmeans", "k-means", "prediction", "regression", "analytics", "forecast", "time series"]):
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
    'Button' look using shields (GitHub-safe).
    """
    label_text = label.replace(" ", "%20")
    base = f"https://img.shields.io/badge/{label_text}-Open-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"

    # No nested f-strings, no escaping needed
    return f'<a href="{url}"><img src="{base}"/></a>'

def short_desc(desc: str | None) -> str:
    if not desc:
        return "Project repository"
    d = " ".join(desc.split())
    if len(d) > 120:
        d = d[:117].rstrip() + "…"
    return escape(d)

def tags_for(repo: dict):
    n = normalize_text(repo.get("name", ""))
    d = normalize_text(repo.get("description", "") or "")
    blob = f"{n} {d}"
    lang = (repo.get("language") or "Project").strip()

    tags = []

    # LLM first
    if any(k in blob for k in ["llm", "rag", "langchain", "embeddings", "agent", "nlp", "transformer"]):
        tags += [badge("GenAI", "LLM", "0EA5E9"), badge("RAG", "Embeddings", "7C3AED")]

    # CV
    if any(k in blob for k in ["computer vision", "cnn", "image", "opencv", "segmentation"]):
        tags += [badge("ComputerVision", "Image", "2563EB"), badge("DeepLearning", "CNN", "7C3AED")]

    # ML/Analytics
    if any(k in blob for k in ["clustering", "kmeans", "prediction", "regression", "analytics", "forecast"]):
        tags += [badge("ML", "Modeling", "16A34A"), badge("Analytics", "Insights", "0EA5E9")]

    # iOS/Swift
    if any(k in blob for k in ["swift", "swiftui", "ios", "websocket", "realtime"]):
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

def repo_card(repo: dict, featured=False) -> str:
    """
    Portfolio-style card inside table cell:
    - title
    - short description
    - meta (stars/forks/updated)
    - action buttons
    - tags
    """
    name = escape(repo["name"])
    url = repo["html_url"]
    desc = short_desc(repo.get("description"))
    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    updated_at = repo.get("pushed_at") or repo.get("updated_at") or ""
    updated_short = updated_at[:10] if updated_at else ""

    tag_line = " ".join(tags_for(repo))

    # Buttons
    repo_btn = button("Repo", url, "1E40AF", "github")
    stars_btn = button(f"Stars%20{stars}", f"{url}/stargazers", "16A34A", "github")

    # Featured marker
    featured_chip = ""
    if featured:
        featured_chip = f'{badge("Featured", "Top%208", "F59E0B")}<br/><br/>'

    return f"""
<td width="50%" valign="top">
  <div>
    <h3>⭐ {name}</h3>
    <p>{desc}</p>
    <sub>⭐ {stars} &nbsp;•&nbsp; 🍴 {forks} &nbsp;•&nbsp; 🕒 {escape(updated_short)}</sub>
    <br/><br/>
    {featured_chip}
    {repo_btn} &nbsp; {stars_btn}
    <br/><br/>
    {tag_line}
  </div>
</td>
""".strip()

def build_table(repos: list[dict], featured=False) -> str:
    rows = []
    for i in range(0, len(repos), 2):
        left = repo_card(repos[i], featured=featured)
        right = repo_card(repos[i + 1], featured=featured) if i + 1 < len(repos) else '<td width="50%"></td>'
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"

def anchor_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

def build_portfolio_projects_block(repos_sorted: list[dict], top_n=8) -> str:
    top = repos_sorted[:top_n]
    rest = repos_sorted[top_n:]

    # Quick nav chips (interactive)
    cats = ["LLM / GenAI", "Computer Vision", "ML / Analytics", "iOS / Swift", "Other"]
    chips = " &nbsp; ".join([f'<a href="#{anchor_id(c)}">{badge("Category", c, "111827")}</a>' for c in cats])

    featured_table = build_table(top, featured=True) if top else "<sub>No public projects found.</sub>"

    if not rest:
        return f"{chips}\n\n{featured_table}"

    # Group rest by category
    buckets = {c: [] for c in cats}
    for r in rest:
        buckets[category_of(r)].append(r)

    grouped_html_parts = []
    for c in cats:
        items = buckets.get(c, [])
        if not items:
            continue
        grouped_html_parts.append(f'<h3 id="{anchor_id(c)}">📌 {escape(c)}</h3>')
        grouped_html_parts.append(build_table(items, featured=False))
        grouped_html_parts.append("<br/>")

    grouped_html = "\n".join(grouped_html_parts).strip()

    collapsible = f"""
<details>
  <summary><b>📚 View all projects ({len(rest)} more)</b></summary>
  <br/>
  {grouped_html}
</details>
""".strip()

    return f"{chips}\n\n{featured_table}\n\n{collapsible}"


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
