import os
import re
import time
import requests
from html import escape

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
    Sorted by recently updated.
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
            # exclude profile repo
            continue
        clean.append(repo)

    return clean


# ----------------------------
# Visual helpers
# ----------------------------
def shields_badge(label, value, color="111827", logo=None):
    """
    Keep your exact badge vibe: for-the-badge + dark labelColor.
    """
    label = label.replace("-", "--").replace(" ", "%20")
    value = value.replace("-", "--").replace(" ", "%20")
    base = f"https://img.shields.io/badge/{label}-{value}-{color}?style=for-the-badge&labelColor=0B1020"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<img src="{base}"/>'


def repo_tags(repo_name: str, language: str | None):
    """
    Return 2–3 concise tags (badges) that look premium and consistent.
    """
    n = repo_name.lower()
    tags = []

    # iOS / Swift
    if any(k in n for k in ["swift", "ios", "swiftui", "chat"]):
        tags += [
            shields_badge("Swift", "SwiftUI", "F05138", "swift"),
            shields_badge("Realtime", "WebSockets", "DC2626"),
        ]

    # CV / Deep Learning
    if any(k in n for k in ["dog", "breed", "wheat", "image", "classification", "cv"]):
        tags += [
            shields_badge("ComputerVision", "Image", "2563EB"),
            shields_badge("DeepLearning", "CNN", "7C3AED"),
        ]

    # Retail / Segmentation / Clustering
    if any(k in n for k in ["fater", "retail", "segmentation", "cluster", "kmeans", "k-means"]):
        tags += [
            shields_badge("ML", "Clustering", "16A34A"),
            shields_badge("Analytics", "Segmentation", "0EA5E9"),
        ]

    # Finance / Stock analysis
    if any(k in n for k in ["stock", "market", "trading", "finance"]):
        tags += [
            shields_badge("Data", "Pipeline", "0EA5E9"),
            shields_badge("Finance", "Analytics", "16A34A"),
        ]

    # Learning analytics / education
    if any(k in n for k in ["oulad", "learning", "student", "education"]):
        tags += [
            shields_badge("ML", "Prediction", "7C3AED"),
            shields_badge("Model", "Evaluation", "16A34A"),
        ]

    # Healthcare / ALS
    if any(k in n for k in ["als", "health", "stroke", "clinical", "medical"]):
        tags += [
            shields_badge("Healthcare", "Analytics", "DC2626"),
            shields_badge("ML", "Prediction", "7C3AED"),
        ]

    # Trip planner / agent / AI assistant
    if any(k in n for k in ["trip", "planner", "assistant", "agent", "chatbot"]):
        tags += [
            shields_badge("AI", "Assistant", "0EA5E9"),
            shields_badge("Product", "Workflow", "16A34A"),
        ]

    # MLOps
    if any(k in n for k in ["mlops", "deployment", "pipeline", "docker"]):
        tags += [
            shields_badge("MLOps", "Pipeline", "16A34A"),
            shields_badge("Deployment", "Ready", "0EA5E9"),
        ]

    # Fallback: use language
    if not tags:
        lang = (language or "Project").strip()
        tags = [shields_badge("Stack", lang, "111827")]

    # return at most 3 for clean visual
    return tags[:3]


def pretty_desc(desc: str | None) -> str:
    """
    Clean, recruiter-friendly short description.
    """
    if not desc:
        return "Project repository"
    d = " ".join(desc.split())
    # keep it short
    if len(d) > 120:
        d = d[:117].rstrip() + "…"
    return escape(d)


def repo_card(repo):
    """
    Premium table cell card. GitHub-safe HTML:
    - uses <div>, <sub>, <br/>, badges
    - no custom CSS, only inline styles (GitHub supports basic)
    """
    name = escape(repo["name"])
    url = repo["html_url"]
    desc = pretty_desc(repo.get("description"))
    lang = repo.get("language")

    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    updated_at = repo.get("updated_at", "")  # ISO
    updated_short = updated_at[:10] if updated_at else ""

    tags = "\n".join(repo_tags(repo["name"], lang))

    meta_row = f"""
<sub>⭐ {stars} &nbsp;•&nbsp; 🍴 {forks} &nbsp;•&nbsp; 🕒 {escape(updated_short)}</sub>
""".strip()

    return f"""
<td width="50%" valign="top">
  <div>
    <h3>⭐ {name}</h3>
    <p>{desc}</p>
    <p>🔗 <a href="{url}">{url}</a></p>
    {meta_row}
    <br/><br/>
    {tags}
  </div>
</td>
""".strip()


def build_table(repos):
    """
    Build a 2-column HTML table from a list of repos.
    """
    rows = []
    for i in range(0, len(repos), 2):
        left = repo_card(repos[i])
        right = repo_card(repos[i + 1]) if i + 1 < len(repos) else '<td width="50%"></td>'
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def build_projects_block(repos, top_n=8):
    """
    Top N shown, rest in collapsible details.
    """
    top = repos[:top_n]
    rest = repos[top_n:]

    top_table = build_table(top) if top else "<sub>No public projects found.</sub>"

    if not rest:
        return top_table

    rest_table = build_table(rest)

    # Collapsible block (keeps your page clean but still shows everything)
    collapsible = f"""
<details>
  <summary><b>📚 View all projects ({len(rest)} more)</b></summary>
  <br/>
  {rest_table}
</details>
""".strip()

    return top_table + "\n\n" + collapsible


# ----------------------------
# README editing
# ----------------------------
def replace_between_markers(text, start, end, replacement):
    pattern = re.compile(rf"({re.escape(start)})(.*?)(\s*{re.escape(end)})", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers not found: {start} ... {end}")
    return pattern.sub(rf"\1\n{replacement}\n\3", text, count=1)


def bump_cache_bust(text):
    # Replace all occurrences so each run forces GitHub to fetch fresh images
    return text.replace("__CACHE_BUST__", str(int(time.time())))


def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    repos = fetch_repos()

    projects_html = build_projects_block(repos, top_n=8)

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
