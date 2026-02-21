import os, re, time, requests

USERNAME = os.environ.get("USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = "README.md"

if not USERNAME:
    raise SystemExit("USERNAME env var is required")

headers = {"Accept": "application/vnd.github+json"}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

def fetch_repos():
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
            continue
        clean.append(repo)
    return clean

def badge(label, value, color="111827", logo=None):
    base = f"https://img.shields.io/badge/{label}-{value}-{color}?style=for-the-badge"
    if logo:
        base += f"&logo={logo}&logoColor=white"
    return f'<img src="{base}"/>'

def tags_for(repo_name, language):
    n = repo_name.lower()
    tags = []

    # Keep your exact visual style (same badge theme)
    if "swift" in n or "ios" in n:
        tags += [badge("Swift", "SwiftUI", "111827", "swift")]

    if "dog" in n or "breed" in n:
        tags += [badge("DeepLearning", "CNN"), badge("ComputerVision", "Images")]

    if "wheat" in n or "classification" in n:
        tags += [badge("CV", "Classification"), badge("DeepLearning", "Modeling")]

    if "stock" in n or "market" in n:
        tags += [badge("Data", "Pipeline"), badge("Financial", "Analytics")]

    if "oulad" in n or "learning-analytics" in n or "open-university" in n:
        tags += [badge("ML", "Prediction"), badge("Model", "Evaluation")]

    if "fater" in n or "retail" in n:
        tags += [badge("ML", "Clustering"), badge("Data", "Analytics")]

    if "als" in n:
        tags += [badge("Health", "Analytics"), badge("ML", "Prediction")]

    # fallback if nothing matched
    if not tags:
        lang = (language or "Project").replace(" ", "%20")
        tags = [badge("Stack", lang)]

    return tags[:2]

def card(repo):
    name = repo["name"]
    url = repo["html_url"]
    desc = (repo.get("description") or "").strip() or "Project repository"
    language = repo.get("language")

    tag_imgs = "\n".join(tags_for(name, language))

    return f"""
<td width="50%" valign="top">

### ⭐ {name}
{desc}

🔗 {url}

{tag_imgs}

</td>
""".strip()

def build_table(repos, limit=6):
    chosen = repos[:limit]
    rows = []
    for i in range(0, len(chosen), 2):
        left = card(chosen[i])
        right = card(chosen[i+1]) if i+1 < len(chosen) else '<td width="50%"></td>'
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"

def replace_between(text, start, end, replacement):
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
    projects_html = build_table(repos, limit=6)

    readme = replace_between(readme, "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->", projects_html)
    readme = bump_cache_bust(readme)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    main()
