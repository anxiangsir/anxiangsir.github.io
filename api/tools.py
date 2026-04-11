"""
Agent tools for the Chat API.

Defines tool schemas (OpenAI function-calling format) and execution functions
for each tool the GPT-5 agent can invoke.
"""

import json
import logging
import os
import re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import yaml

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────
_API_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_API_DIR, ".."))
_PAGES_DIR = os.path.join(_ROOT_DIR, "pages")
_DATA_DIR = os.path.join(_ROOT_DIR, "data")
_PUBLICATIONS_YAML = os.path.join(_DATA_DIR, "research_data.yaml")
_CITATION_DATA_JSON = os.path.join(_DATA_DIR, "citation_data.json")

# ── Proxy for external requests ──────────────────────────────────────────
_PROXY = os.getenv("http_proxy", os.getenv("HTTP_PROXY", ""))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = "anxiangsir"


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schemas  (OpenAI function-calling format)
# ═══════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_publications",
            "description": (
                "Search Xiang An's publications by keyword. Returns matching papers "
                "with title, authors, venue, URLs, and summary. Use this when the user "
                "asks about specific papers, research topics, or academic work. "
                "IMPORTANT: When users ask about paper authors, ALWAYS follow up by using "
                "fetch_webpage on the paper's arxiv URL to verify the complete author list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'PartialFC', 'face recognition', 'multimodal')",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": (
                "Fetch and extract the main text content from any webpage URL. "
                "Returns clean markdown text. Use this to read paper pages, blog posts, "
                "project homepages, or any online content the user mentions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to fetch (e.g. 'https://arxiv.org/abs/2203.15565')",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_github_repo",
            "description": (
                "Search within a specific GitHub repository owned by anxiangsir or "
                "related organizations. Can read README, search code files, or list "
                "directory contents. Use this when the user asks about code, "
                "implementations, or repo structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository in 'owner/name' format (e.g. 'deepinsight/insightface')",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path within the repo (default: '' for root). Use 'README.md' to read the README.",
                    },
                },
                "required": ["repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_github_repos",
            "description": (
                "List public GitHub repositories for a user or organization. "
                "Returns repo name, description, stars, and language. Use this to "
                "find which repos exist or to get an overview of someone's GitHub."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "GitHub username or org (default: 'anxiangsir')",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["stars", "updated", "created"],
                        "description": "Sort order (default: 'stars')",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_citation_stats",
            "description": (
                "Get citation statistics for Xiang An's publications. Returns total "
                "citations, number of citing countries, top institutions, and geographic "
                "distribution. Use this when the user asks about impact, citations, "
                "or academic influence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "detail_level": {
                        "type": "string",
                        "enum": ["summary", "by_country", "top_institutions"],
                        "description": "Level of detail: 'summary' for overview, 'by_country' for per-country counts, 'top_institutions' for top citing institutions.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_site_page",
            "description": (
                "Read an HTML page from Xiang An's personal website. Extracts the "
                "text content. Available pages include: partial_fc, llava_onevision2, "
                "video_codec, publications, blog, chat, yarn, areal, ddpm, "
                "diffusion_models, funasr, gae, mario, megatron_fp8, "
                "monte_carlo_method, rabitq, verl_grpo, video_subtitle_benchmark. "
                "Use this to answer questions about specific visualizations or pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page_name": {
                        "type": "string",
                        "description": "Page name without extension (e.g. 'partial_fc', 'publications'). Use 'index' for the homepage.",
                    }
                },
                "required": ["page_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pinned_repos",
            "description": (
                "Get pinned repositories for a GitHub user. Pinned repos are the ones "
                "the user has chosen to showcase on their profile. Returns repo name, "
                "description, URL, stars, forks, and primary language. Use this when "
                "the user asks about someone's featured or pinned GitHub projects."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "GitHub username (default: 'anxiangsir')",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_site_pages",
            "description": (
                "Search across all pages on Xiang An's personal website by keyword. "
                "Returns matching page titles and relevant text excerpts. Use this when "
                "the user asks about blog posts, interactive visualizations, or any "
                "content on the site. For example, searching 'PartialFC' will find the "
                "PartialFC interactive visualization page and blog entries about it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword (e.g. 'PartialFC', 'diffusion', 'video codec')",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_contributors",
            "description": (
                "Get the list of contributors for a GitHub repository. Returns each "
                "contributor's username, avatar URL, number of commits, and profile link. "
                "Use this when the user asks about who contributed to a repo, code authors, "
                "or development team behind a project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository in 'owner/name' format (e.g. 'deepinsight/insightface')",
                    }
                },
                "required": ["repo"],
            },
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Tool Implementations
# ═══════════════════════════════════════════════════════════════════════════

# ── Cached data loaders ──────────────────────────────────────────────────
_publications_cache = None
_citation_cache = None


def _load_publications():
    """Load publications from YAML (cached)."""
    global _publications_cache
    if _publications_cache is not None:
        return _publications_cache
    try:
        with open(_PUBLICATIONS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _publications_cache = data.get("publications", [])
    except Exception as e:
        logger.warning(f"Failed to load research_data.yaml: {e}")
        _publications_cache = []
    return _publications_cache


def _load_citation_data():
    """Load citation data from JSON (cached)."""
    global _citation_cache
    if _citation_cache is not None:
        return _citation_cache
    try:
        with open(_CITATION_DATA_JSON, "r", encoding="utf-8") as f:
            _citation_cache = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load citation_data.json: {e}")
        _citation_cache = {}
    return _citation_cache


# ── Helper: HTTP request with proxy support ──────────────────────────────

def _http_get(url, headers=None, timeout=15):
    """Perform an HTTP GET with optional proxy."""
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; XiangAnBot/1.0)")
    req = Request(url, headers=headers)

    if _PROXY and not any(h in url for h in ("localhost", "127.0.0.1")):
        from urllib.request import ProxyHandler, build_opener
        opener = build_opener(ProxyHandler({"http": _PROXY, "https": _PROXY}))
        return opener.open(req, timeout=timeout).read()
    else:
        return urlopen(req, timeout=timeout).read()


def _http_post(url, data, headers=None, timeout=15):
    """Perform an HTTP POST with optional proxy."""
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; XiangAnBot/1.0)")
    headers.setdefault("Content-Type", "application/json")
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST")

    if _PROXY and not any(h in url for h in ("localhost", "127.0.0.1")):
        from urllib.request import ProxyHandler, build_opener
        opener = build_opener(ProxyHandler({"http": _PROXY, "https": _PROXY}))
        return opener.open(req, timeout=timeout).read()
    else:
        return urlopen(req, timeout=timeout).read()


# ── 1. search_publications ───────────────────────────────────────────────

def _search_publications(query: str) -> str:
    """Search publications by keyword using simple text matching."""
    pubs = _load_publications()
    if not pubs:
        return "No publications data available."

    query_lower = query.lower()
    query_terms = [t for t in re.split(r'\W+', query_lower) if t]

    scored = []
    for pub in pubs:
        searchable = " ".join(
            str(pub.get(k, "")) for k in
            ("title", "authors", "venue", "summary", "year")
        ).lower()
        score = sum(1 for term in query_terms if term in searchable)
        # Bonus for title match
        title_lower = pub.get("title", "").lower()
        score += sum(2 for term in query_terms if term in title_lower)
        if score > 0:
            scored.append((score, pub))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:5]

    if not results:
        return f"No publications found matching '{query}'."

    lines = [f"Found {len(results)} publication(s) matching '{query}':\n"]
    for _score, pub in results:
        lines.append(f"**{pub.get('title', 'Untitled')}**")
        if pub.get("authors"):
            lines.append(f"  Authors: {pub['authors']}")
        if pub.get("venue"):
            lines.append(f"  Venue: {pub['venue']}")
        if pub.get("paper_url"):
            lines.append(f"  Paper: {pub['paper_url']}")
            lines.append(f"  [NOTE: Use fetch_webpage on {pub['paper_url']} to verify complete author list from arxiv]")
        if pub.get("code_url"):
            lines.append(f"  Code: {pub['code_url']}")
        if pub.get("homepage_url"):
            lines.append(f"  Homepage: {pub['homepage_url']}")
        if pub.get("summary"):
            summary = pub["summary"].strip()
            if len(summary) > 300:
                summary = summary[:300] + "..."
            lines.append(f"  Summary: {summary}")
        media = pub.get("media_links", [])
        if media:
            ml_str = ", ".join(f"{m['name']}: {m['url']}" for m in media if m.get("name"))
            lines.append(f"  Media: {ml_str}")
        lines.append("")

    return "\n".join(lines)


# ── 2. fetch_webpage ─────────────────────────────────────────────────────

def _fetch_webpage(url: str) -> str:
    """Fetch webpage and extract content as markdown."""
    try:
        import trafilatura
        raw = _http_get(url, timeout=20)
        text = trafilatura.extract(
            raw,
            output_format="markdown",
            favor_precision=True,
            include_links=True,
            include_tables=True,
        )
        if text:
            # Truncate for LLM context
            if len(text) > 8000:
                text = text[:8000] + "\n\n... [content truncated]"
            return f"Content from {url}:\n\n{text}"
        return f"Could not extract meaningful content from {url}."
    except ImportError:
        # Fallback: basic HTML text extraction without trafilatura
        try:
            raw = _http_get(url, timeout=20)
            html_text = raw.decode("utf-8", errors="replace")
            # Strip HTML tags
            clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html_text)
            clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', clean)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) > 8000:
                clean = clean[:8000] + "... [truncated]"
            return f"Content from {url} (basic extraction):\n\n{clean}"
        except Exception as e:
            return f"Failed to fetch {url}: {e}"
    except Exception as e:
        return f"Failed to fetch {url}: {e}"


# ── 3. search_github_repo ───────────────────────────────────────────────

def _search_github_repo(repo: str, path: str = "") -> str:
    """Read file or list directory in a GitHub repo via API."""
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        raw = _http_get(api_url, headers=headers, timeout=15)
        data = json.loads(raw.decode("utf-8"))

        if isinstance(data, list):
            # Directory listing
            entries = []
            for item in data[:50]:  # limit entries
                icon = "📁" if item["type"] == "dir" else "📄"
                size = f" ({item.get('size', 0)} bytes)" if item["type"] == "file" else ""
                entries.append(f"  {icon} {item['name']}{size}")
            return f"Contents of {repo}/{path or '(root)'}:\n" + "\n".join(entries)

        elif isinstance(data, dict) and data.get("type") == "file":
            # File content (base64 encoded)
            import base64
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
            if len(content) > 8000:
                content = content[:8000] + "\n\n... [file truncated]"
            return f"File: {repo}/{path}\n\n{content}"

        return f"Unexpected response from GitHub API for {repo}/{path}."
    except HTTPError as e:
        if e.code == 404:
            return f"Path '{path}' not found in repo '{repo}'."
        return f"GitHub API error for {repo}/{path}: HTTP {e.code}"
    except Exception as e:
        return f"Failed to access {repo}/{path}: {e}"


# ── 4. list_github_repos ────────────────────────────────────────────────

def _list_github_repos(username: str = "", sort: str = "stars") -> str:
    """List public repos for a GitHub user."""
    username = username or GITHUB_USERNAME
    sort_param = "stars" if sort == "stars" else sort
    direction = "desc" if sort == "stars" else "desc"
    api_url = (
        f"https://api.github.com/users/{username}/repos"
        f"?type=public&sort={sort_param}&direction={direction}&per_page=30"
    )
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        raw = _http_get(api_url, headers=headers, timeout=15)
        repos = json.loads(raw.decode("utf-8"))

        if not repos:
            return f"No public repositories found for {username}."

        lines = [f"Public repositories for **{username}** ({len(repos)} shown):\n"]
        for r in repos:
            stars = r.get("stargazers_count", 0)
            desc = r.get("description", "") or ""
            lang = r.get("language", "") or ""
            fork = " (fork)" if r.get("fork") else ""
            lines.append(f"- **{r['name']}**{fork} ⭐{stars} [{lang}]")
            if desc:
                lines.append(f"  {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list repos for {username}: {e}"


# ── 5. get_citation_stats ───────────────────────────────────────────────

def _get_citation_stats(detail_level: str = "summary") -> str:
    """Get citation statistics."""
    data = _load_citation_data()
    if not data:
        return "Citation data is not available."

    total = data.get("total_citations", 0)
    n_countries = data.get("total_countries", 0)
    n_institutions = data.get("total_institutions", 0)
    countries = data.get("countries", {})

    lines = [
        "**Citation Statistics for Xiang An**",
        f"- Total citations: {total:,}",
        f"- Citing countries: {n_countries}",
        f"- Citing institutions: {n_institutions}",
        f"- Google Scholar: https://scholar.google.com.hk/citations?hl=en&user=1ckaPgwAAAAJ",
    ]

    if detail_level == "by_country":
        lines.append("\n**Citations by Country (top 20):**")
        sorted_countries = sorted(
            countries.items(), key=lambda x: x[1].get("count", 0), reverse=True
        )
        for code, info in sorted_countries[:20]:
            name = info.get("name", code)
            count = info.get("count", 0)
            n_inst = len(info.get("institutions", []))
            lines.append(f"  {name}: {count} citations from {n_inst} institutions")

    elif detail_level == "top_institutions":
        lines.append("\n**Top Citing Institutions:**")
        all_institutions = []
        for _code, cinfo in countries.items():
            country_name = cinfo.get("name", "")
            for inst in cinfo.get("institutions", []):
                all_institutions.append({
                    "name": inst["name"],
                    "count": inst["count"],
                    "country": country_name,
                })
        all_institutions.sort(key=lambda x: x["count"], reverse=True)
        for inst in all_institutions[:30]:
            lines.append(f"  {inst['name']} ({inst['country']}): {inst['count']} citations")

    return "\n".join(lines)


# ── 7. get_pinned_repos ────────────────────────────────────────────────

def _get_pinned_repos(username: str = "") -> str:
    """Get pinned repos for a GitHub user via GraphQL API."""
    username = username or GITHUB_USERNAME
    if not GITHUB_TOKEN:
        return "GitHub token not configured. Cannot query pinned repos (requires GraphQL API)."

    query = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              description
              url
              stargazerCount
              forkCount
              primaryLanguage { name }
            }
          }
        }
      }
    }
    """

    try:
        raw = _http_post(
            "https://api.github.com/graphql",
            data={"query": query, "variables": {"login": username}},
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        result = json.loads(raw.decode("utf-8"))

        if "errors" in result:
            return f"GitHub GraphQL error: {result['errors'][0].get('message', 'unknown')}"

        nodes = result.get("data", {}).get("user", {}).get("pinnedItems", {}).get("nodes", [])
        if not nodes:
            return f"No pinned repositories found for {username}."

        lines = [f"Pinned repositories for **{username}** ({len(nodes)} repos):\n"]
        for repo in nodes:
            name = repo.get("name", "unknown")
            desc = repo.get("description", "") or ""
            url = repo.get("url", "")
            stars = repo.get("stargazerCount", 0)
            forks = repo.get("forkCount", 0)
            lang = repo.get("primaryLanguage", {}) or {}
            lang_name = lang.get("name", "") or ""
            lines.append(f"- **{name}** ⭐{stars} 🍴{forks} [{lang_name}]")
            if desc:
                lines.append(f"  {desc}")
            if url:
                lines.append(f"  {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get pinned repos for {username}: {e}"

# ── 7.6. get_repo_contributors ────────────────────────────────────────

def _get_repo_contributors(repo: str) -> str:
    """Get contributors for a GitHub repository via REST API."""
    if not repo or "/" not in repo:
        return "Please provide a repo in 'owner/name' format (e.g. 'deepinsight/insightface')."

    api_url = f"https://api.github.com/repos/{repo}/contributors?per_page=30"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        raw = _http_get(api_url, headers=headers, timeout=15)
        data = json.loads(raw.decode("utf-8"))

        if not isinstance(data, list):
            return f"Unexpected response from GitHub API for {repo} contributors."

        if not data:
            return f"No contributors found for {repo}. The repo may be empty or not exist."

        lines = [f"Contributors for {repo} ({len(data)} total):\n"]
        for i, c in enumerate(data, 1):
            login = c.get("login", "unknown")
            contribs = c.get("contributions", 0)
            profile = c.get("html_url", f"https://github.com/{login}")
            avatar = c.get("avatar_url", "")
            lines.append(
                f"{i}. **{login}** — {contribs} commits  "
                f"(profile: {profile})"
            )
        return "\n".join(lines)
    except HTTPError as e:
        if e.code == 404:
            return f"Repository '{repo}' not found on GitHub."
        return f"GitHub API error for {repo} contributors: HTTP {e.code}"
    except Exception as e:
        return f"Failed to get contributors for {repo}: {e}"

# ── 7.5. search_site_pages ─────────────────────────────────────────────

def _search_site_pages(query: str) -> str:
    """Search all site pages by keyword and return matching excerpts."""
    query_lower = query.lower()
    query_terms = [t for t in re.split(r'\W+', query_lower) if t]
    if not query_terms:
        return "Please provide a search query."

    results = []

    # Collect all HTML files: index.html + pages/*.html
    html_files = []
    index_path = os.path.join(_ROOT_DIR, "index.html")
    if os.path.exists(index_path):
        html_files.append(("index", index_path))
    if os.path.isdir(_PAGES_DIR):
        for fname in os.listdir(_PAGES_DIR):
            if fname.endswith(".html") and fname != "chat.html":
                html_files.append((fname.replace(".html", ""), os.path.join(_PAGES_DIR, fname)))

    for page_name, filepath in html_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()
            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1) if title_match else page_name
            # Strip script/style/tags
            clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
            clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', clean)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            clean_lower = clean.lower()
            # Score: count term hits, bonus for title match
            score = sum(clean_lower.count(term) for term in query_terms)
            title_lower = title.lower()
            score += sum(10 for term in query_terms if term in title_lower)
            if score > 0:
                # Extract a relevant snippet around the first match
                snippet = ""
                for term in query_terms:
                    idx = clean_lower.find(term)
                    if idx >= 0:
                        start = max(0, idx - 100)
                        end = min(len(clean), idx + len(term) + 200)
                        snippet = "..." + clean[start:end].strip() + "..."
                        break
                results.append((score, page_name, title, snippet))
        except Exception:
            continue

    results.sort(key=lambda x: x[0], reverse=True)
    top = results[:8]

    if not top:
        return f"No site pages found matching '{query}'."

    lines = [f"Found {len(top)} page(s) matching '{query}':\n"]
    for _score, page_name, title, snippet in top:
        page_url = f"/pages/{page_name}.html" if page_name != "index" else "/index.html"
        lines.append(f"**{title}** ({page_url})")
        if snippet:
            lines.append(f"  {snippet}")
        lines.append("")
    return "\n".join(lines)


# ── 6. read_site_page ───────────────────────────────────────────────────

def _read_site_page(page_name: str) -> str:
    """Read an HTML page from the site and extract text content."""
    page_name = page_name.strip().lower().replace(".html", "")

    if page_name == "index":
        filepath = os.path.join(_ROOT_DIR, "index.html")
    else:
        filepath = os.path.join(_PAGES_DIR, f"{page_name}.html")

    if not os.path.exists(filepath):
        available = [
            f.replace(".html", "")
            for f in os.listdir(_PAGES_DIR)
            if f.endswith(".html")
        ]
        return (
            f"Page '{page_name}' not found. Available pages: "
            + ", ".join(sorted(available))
            + ", index"
        )

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()

        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else page_name

        # Strip script and style tags, then HTML tags
        clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
        clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', clean)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        if len(clean) > 6000:
            clean = clean[:6000] + "... [page content truncated]"

        return f"Page: {title}\n\n{clean}"
    except Exception as e:
        return f"Failed to read page '{page_name}': {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Tool Dispatcher
# ═══════════════════════════════════════════════════════════════════════════

_TOOL_MAP = {
    "search_publications": lambda args: _search_publications(args.get("query", "")),
    "fetch_webpage": lambda args: _fetch_webpage(args.get("url", "")),
    "search_github_repo": lambda args: _search_github_repo(
        args.get("repo", ""), args.get("path", "")
    ),
    "list_github_repos": lambda args: _list_github_repos(
        args.get("username", ""), args.get("sort", "stars")
    ),
    "get_citation_stats": lambda args: _get_citation_stats(
        args.get("detail_level", "summary")
    ),
    "read_site_page": lambda args: _read_site_page(args.get("page_name", "")),
    "search_site_pages": lambda args: _search_site_pages(args.get("query", "")),
    "get_pinned_repos": lambda args: _get_pinned_repos(args.get("username", "")),
    "get_repo_contributors": lambda args: _get_repo_contributors(args.get("repo", "")),
}

# Friendly display names for the frontend
TOOL_DISPLAY = {
    "search_publications": {"icon": "🔍", "label": "Searching publications"},
    "fetch_webpage": {"icon": "🌐", "label": "Fetching webpage"},
    "search_github_repo": {"icon": "📂", "label": "Browsing GitHub repo"},
    "list_github_repos": {"icon": "📋", "label": "Listing GitHub repos"},
    "get_citation_stats": {"icon": "📊", "label": "Loading citation stats"},
    "read_site_page": {"icon": "📄", "label": "Reading site page"},
    "search_site_pages": {"icon": "🔎", "label": "Searching site pages"},
    "get_pinned_repos": {"icon": "📌", "label": "Getting pinned repos"},
    "get_repo_contributors": {"icon": "👥", "label": "Fetching contributors"},
}

def execute_tool(name: str, arguments_json: str) -> str:
    """Execute a tool by name. Returns the result string.

    Args:
        name: Tool function name.
        arguments_json: JSON string of arguments.
    """
    func = _TOOL_MAP.get(name)
    if func is None:
        return f"Unknown tool: {name}"

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return f"Invalid arguments JSON for tool {name}."

    try:
        return func(args)
    except Exception as e:
        logger.exception(f"Tool execution error: {name}")
        return f"Tool '{name}' failed: {e}"
