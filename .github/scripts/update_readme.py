"""
update_readme.py — regenerates the Featured Projects section of the profile README.

What it does
  • Reads every public, non-fork repo owned by USERNAME
  • Renders curated project cards between <!-- PROJECTS:START --> and <!-- PROJECTS:END -->
  • Each card uses the overview in PROJECTS below; repos without an entry still get a
    clean card built from their GitHub description (so new repos never look empty)
  • Refreshes the cache-buster (?v=...) on the analytics images

To add / edit a project overview: add an entry to PROJECTS (key = exact repo name).
"""

import os
import re
import time
from html import escape
from urllib.parse import quote

import requests

USERNAME = os.environ.get("USERNAME", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
README_PATH = "README.md"
TOP_N = 6  # cards shown before the "More projects" fold

if not USERNAME:
    raise SystemExit("USERNAME env var is required")

HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Repos that are not portfolio projects
EXCLUDE = {USERNAME.lower(), "navyashreebyregowda", "draft-of-ui-design"}

# ---------------------------------------------------------------------------
# Curated project overviews.  order = position on the profile (lower first).
# stack items: (label, hex color, simple-icons logo or None)
# ---------------------------------------------------------------------------
PROJECTS = {
    "Fitspyre": {
        "order": 1,
        "title": "Fitspyre — AI Fitness Coach",
        "category": "iOS · On-device AI",
        "summary": "AI-powered iOS + watchOS fitness app that builds personalised workout and "
                   "nutrition plans from an onboarding questionnaire and coaches form in real time "
                   "using on-device pose detection.",
        "highlights": [
            "Live rep counting & form alerts with Vision body-pose tracking",
            "Rule-based plan, nutrition and safety engines; HealthKit + Apple Watch sync",
        ],
        "stack": [("Swift", "F05138", "swift"), ("SwiftUI", "0D96F6", "swift"),
                  ("Vision", "111827", "apple"), ("HealthKit", "FF2D55", "apple"),
                  ("SwiftData", "111827", None)],
    },
    "AI-Trip-Planner": {
        "order": 2,
        "title": "AI Trip Planner — Agentic Travel Assistant",
        "category": "GenAI · AI Agents",
        "summary": "LLM agent built with LangGraph that turns a destination, budget and dates into a "
                   "complete day-by-day itinerary, calling live tools for places, weather, currency "
                   "conversion and cost estimation.",
        "highlights": [
            "Tool-calling agent graph (LangGraph) with modular tool layer",
            "FastAPI backend + Streamlit front-end, exports plan to a document",
        ],
        "stack": [("Python", "3776AB", "python"), ("LangGraph", "1C3C3C", "langchain"),
                  ("FastAPI", "009688", "fastapi"), ("Streamlit", "FF4B4B", "streamlit")],
    },
    "Stroke-prediction": {
        "order": 3,
        "title": "Stroke Risk Intelligence",
        "category": "Healthcare ML · Deployment",
        "summary": "End-to-end ML system that predicts stroke risk from patient health indicators. "
                   "Benchmarks five classifiers with a recall-first selection rule to minimise missed "
                   "high-risk patients, served through a Flask web app.",
        "highlights": [
            "LR · DT · RF · KNN · GB compared on recall, F1 and ROC-AUC",
            "Dockerised Flask app with MLflow experiment tracking",
        ],
        "stack": [("Python", "3776AB", "python"), ("scikit--learn", "F7931E", "scikitlearn"),
                  ("Flask", "000000", "flask"), ("Docker", "2496ED", "docker"),
                  ("MLflow", "0194E2", "mlflow")],
    },
    "MLOPS_PROJECT": {
        "order": 4,
        "title": "MLOps Pipeline System",
        "category": "MLOps · Production ML",
        "summary": "Production-style ML lifecycle: modular components for data ingestion, validation, "
                   "transformation, training and prediction, wired into config-driven train / predict "
                   "pipelines with structured logging and a serving app.",
        "highlights": [
            "Reusable src/components + src/pipeline package layout",
            "YAML configuration, logging and packaging via setup.py",
        ],
        "stack": [("Python", "3776AB", "python"), ("scikit--learn", "F7931E", "scikitlearn"),
                  ("Flask", "000000", "flask"), ("YAML", "CB171E", "yaml")],
    },
    "Dog-breed-classifier": {
        "order": 5,
        "title": "Dog Breed Classifier",
        "category": "Computer Vision · Deep Learning",
        "summary": "Image-recognition pipeline that first detects whether a photo contains a dog or a "
                   "human face, then predicts the dog breed with a transfer-learning CNN.",
        "highlights": [
            "ResNet50 transfer learning — 82.9% test accuracy",
            "OpenCV face detector as an input gate (dog / human / invalid)",
        ],
        "stack": [("Python", "3776AB", "python"), ("TensorFlow", "FF6F00", "tensorflow"),
                  ("Keras", "D00000", "keras"), ("OpenCV", "5C3EE8", "opencv")],
    },
    "Wheat-growth-stage-classification-": {
        "order": 6,
        "title": "Wheat Growth Stage Classification",
        "category": "Computer Vision · AgriTech",
        "summary": "Deep-learning image classifier that identifies the growth stage of wheat crops from "
                   "field images, supporting precision-agriculture monitoring. Includes a technical "
                   "report with learning curves and confusion-matrix analysis.",
        "highlights": [
            "CNN-based multi-class stage prediction (softmax head)",
            "Full preprocess → train → evaluate workflow and write-up",
        ],
        "stack": [("Python", "3776AB", "python"), ("TensorFlow", "FF6F00", "tensorflow"),
                  ("Keras", "D00000", "keras"), ("OpenCV", "5C3EE8", "opencv")],
    },
    "BigData-Mod-B-OULAD---Open-university-learning-analytics-dataset": {
        "order": 7,
        "title": "OULAD Learning Analytics",
        "category": "Big Data · Classification",
        "summary": "Predicts student outcomes (pass / fail / withdrawal) on the Open University Learning "
                   "Analytics Dataset to flag at-risk learners early, with an interactive Streamlit "
                   "dashboard for exploring the results.",
        "highlights": [
            "Feature engineering across demographics, assessments and VLE activity",
            "Streamlit dashboard + report and presentation",
        ],
        "stack": [("Python", "3776AB", "python"), ("Pandas", "150458", "pandas"),
                  ("scikit--learn", "F7931E", "scikitlearn"), ("Streamlit", "FF4B4B", "streamlit")],
    },
    "BigData-Mod-A-Stock-Market-Analysis-": {
        "order": 8,
        "title": "Real-Time Stock Market Analysis",
        "category": "Big Data · Streaming",
        "summary": "Streaming data pipeline that pulls live market data with yfinance, publishes it "
                   "through an Apache Kafka producer / consumer and analyses trends, moving averages "
                   "and volatility.",
        "highlights": [
            "Kafka producer → consumer streaming architecture",
            "Time-series trend and volatility analysis in Jupyter",
        ],
        "stack": [("Python", "3776AB", "python"), ("Apache Kafka", "231F20", "apachekafka"),
                  ("Pandas", "150458", "pandas"), ("Jupyter", "F37626", "jupyter")],
    },
    "DropSpot": {
        "order": 9,
        "title": "DropSpot — Location-Based AR Social App",
        "category": "iOS · AR",
        "summary": "AR social platform where users pin photo ‘PhotoCards’ to real-world places; friends "
                   "discover them on a map and relive them in augmented reality when they are nearby.",
        "highlights": [
            "ARKit / RealityKit placement with persistent AR anchors",
            "MapKit discovery + CoreLocation proximity, SwiftData storage",
        ],
        "stack": [("SwiftUI", "0D96F6", "swift"), ("ARKit", "111827", "apple"),
                  ("RealityKit", "111827", "apple"), ("MapKit", "111827", "apple")],
    },
    "Swiftchat": {
        "order": 10,
        "title": "SwiftChat — Real-Time Messaging",
        "category": "iOS · Realtime",
        "summary": "Real-time iOS chat app built on WebSockets with a clean MVVM + Repository "
                   "architecture, typing indicators and reactive state management with Combine.",
        "highlights": [
            "Protocol-first WebSocket client and message repository",
            "SwiftUI chat UI: bubbles, composer, typing indicator",
        ],
        "stack": [("Swift", "F05138", "swift"), ("SwiftUI", "0D96F6", "swift"),
                  ("Combine", "111827", None), ("WebSockets", "DC2626", None)],
    },
    "CH-5-Gin-Tonic": {
        "order": 11,
        "title": "Starmy — Interactive Learning App",
        "category": "iOS · EdTech",
        "summary": "Playful SwiftUI app that teaches young children the alphabet through finger "
                   "tracing, 3D object association (USDZ models) and instant visual feedback.",
        "highlights": [
            "Touch-tracing canvas with letter-by-letter feedback",
            "3D objects rendered from USDZ assets",
        ],
        "stack": [("SwiftUI", "0D96F6", "swift"), ("RealityKit", "111827", "apple"),
                  ("Xcode", "147EFB", "xcode")],
    },
    "FATER_CHALLENGE": {
        "order": 12,
        "title": "FATER Challenge — Retail Store Segmentation",
        "category": "Data Science · Clustering",
        "summary": "Business-analytics challenge segmenting retail stores by performance with "
                   "K-Means clustering and translating each segment into concrete commercial actions.",
        "highlights": [
            "Unsupervised segmentation of store performance data",
            "Insight-driven recommendations presented to the company",
        ],
        "stack": [("R", "276DC3", "r"), ("R Markdown", "75AADB", "rstudioide"),
                  ("K--Means", "111827", None)],
    },
    "SwiftChat_": {
        "order": 13,
        "title": "SwiftChat (v1 prototype)",
        "category": "iOS · Prototype",
        "summary": "First iteration of SwiftChat: core chat data models (users, messages with image "
                   "and GIF attachments) and theming, later evolved into the real-time SwiftChat app.",
        "highlights": [
            "Message model with photo / GIF attachments",
            "Theme system shared with SwiftChat",
        ],
        "stack": [("Swift", "F05138", "swift"), ("SwiftUI", "0D96F6", "swift")],
    },
}

LANG_COLORS = {
    "Python": ("3776AB", "python"), "Jupyter Notebook": ("F37626", "jupyter"),
    "Swift": ("F05138", "swift"), "R": ("276DC3", "r"), "HTML": ("E34F26", "html5"),
    "JavaScript": ("F7DF1E", "javascript"), "TypeScript": ("3178C6", "typescript"),
}


# ---------------------------------------------------------------------------
def fetch_repos():
    url = f"https://api.github.com/users/{USERNAME}/repos"
    params = {"per_page": 100, "sort": "updated", "type": "owner"}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return [
        repo for repo in r.json()
        if not (repo.get("private") or repo.get("fork") or repo.get("archived"))
        and repo["name"].lower() not in EXCLUDE
    ]


def sort_repos(repos):
    def key(repo):
        meta = PROJECTS.get(repo["name"])
        if meta:
            return (0, meta["order"], "")
        # un-curated repos: most recently pushed first, after curated ones
        return (1, 0, "".join(chr(255 - ord(c)) for c in (repo.get("pushed_at") or "")))
    return sorted(repos, key=key)


def chip(label, color, logo=None):
    url = f"https://img.shields.io/badge/-{quote(label)}-{color}?style=flat-square"
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f'<img src="{url}" alt="{escape(label.replace("--", "-"))}"/>'


def pretty_name(name):
    return re.sub(r"[-_]+", " ", name).strip()


def card(repo):
    name, url = repo["name"], repo["html_url"]
    meta = PROJECTS.get(name)
    stars = repo.get("stargazers_count", 0) or 0
    pushed = (repo.get("pushed_at") or "")[:7]

    if meta:
        title, category, summary = meta["title"], meta["category"], meta["summary"]
        highlights, stack = meta["highlights"], meta["stack"]
    else:
        title = pretty_name(name)
        lang = repo.get("language") or "Project"
        category = lang
        summary = (repo.get("description") or "").strip() or \
            f"{pretty_name(name)} — see the repository for full details and documentation."
        highlights = []
        color, logo = LANG_COLORS.get(lang, ("111827", None))
        stack = [(lang, color, logo)]

    hl = ""
    if highlights:
        hl = "<ul>\n" + "\n".join(f"  <li>{escape(h)}</li>" for h in highlights) + "\n</ul>\n"
    chips = " ".join(chip(*s) for s in stack)
    meta_line = f"⭐ {stars}" + (f" &nbsp;·&nbsp; Updated {pushed}" if pushed else "")

    return (
        '<td width="50%" valign="top">\n\n'
        f"<sub><b>{escape(category.upper())}</b></sub>\n"
        f'<h3><a href="{url}">{escape(title)}</a></h3>\n'
        f"<p>{escape(summary)}</p>\n"
        f"{hl}"
        f"<p>{chips}</p>\n"
        f'<sub>{meta_line} &nbsp;·&nbsp; <a href="{url}"><b>View repository →</b></a></sub>\n\n'
        "</td>"
    )


def table(repos):
    rows = []
    for i in range(0, len(repos), 2):
        left = card(repos[i])
        right = card(repos[i + 1]) if i + 1 < len(repos) else '<td width="50%"></td>'
        rows.append(f"<tr>\n{left}\n{right}\n</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def build_block(repos):
    top, rest = repos[:TOP_N], repos[TOP_N:]
    out = table(top) if top else "<sub>No public projects found.</sub>"
    if rest:
        out += (
            "\n\n<details>\n"
            f"<summary><b>📂 More projects ({len(rest)})</b></summary>\n<br/>\n\n"
            f"{table(rest)}\n\n</details>"
        )
    return out


def replace_block(text, start, end, body):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Markers not found: {start} ... {end}")
    # exactly one newline each side -> no blank-line build-up between runs
    return pattern.sub(lambda _: f"{start}\n{body}\n{end}", text, count=1)


def main():
    with open(README_PATH, encoding="utf-8") as f:
        readme = f.read()

    repos = sort_repos(fetch_repos())
    readme = replace_block(readme, "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->", build_block(repos))
    readme = re.sub(r"([?&]v=)\d+", lambda m: m.group(1) + str(int(time.time())), readme)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)


if __name__ == "__main__":
    main()
