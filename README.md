# [Xiang An's Personal Homepage](https://anxiangsir.github.io/)

## Features

- Responsive personal homepage with research profile (Wikipedia-style layout)
- Bilingual support (English / 中文) with one-click language toggle
- **AI Agent chat assistant** — Kimi K2.5 with function calling, SSE streaming, and Claude Code-style dark UI
- 10 agent tools: publication search, webpage fetching, GitHub repo browsing, citation stats, site search, and more
- Lightweight RAG retrieval over `research_data.yaml` (publications + GitHub projects)
- Word-level blurIn streaming animation (ChatGPT-grade fluidity)
- Interactive visualizations: PartialFC training pipeline, video codec pipeline, LLaVA-OneVision2 codec animation, and more
- Citation World Map: citing-author geographic distribution from Semantic Scholar (offline-generated)
- Visitor tracking with geographic heatmap (Vercel serverless + Neon Postgres)
- KaTeX SSR build for math-heavy pages (zero runtime math JS)
- Hybrid deployment: GitHub Pages (static) + Vercel (API + Database)

## Project Structure

```
anxiangsir.github.io/
├── index.html                 # Homepage (Wikipedia-style layout, bilingual en/zh)
│
├── pages/                     # HTML pages (non-index)
│   ├── chat.html              #   AI Agent chat (Claude Code dark UI, SSE streaming)
│   ├── partial_fc.html        #   PartialFC interactive visualization
│   ├── llava_onevision2.html  #   LLaVA-OneVision2 codec animation
│   ├── video_codec.html       #   Video codec pipeline + Bitcost scoring system
│   ├── video_subtitle_benchmark.html  # Video subtitle benchmark
│   ├── verl_grpo.html         #   VERL GRPO / DPO / PPO visualization
│   ├── blog.html              #   Blog index
│   ├── publications.html      #   Publications page
│   ├── yarn.html              #   YaRN visualization
│   ├── areal.html             #   Areal interpolation
│   ├── ddpm.html              #   DDPM diffusion
│   ├── diffusion_models.html  #   Diffusion models overview
│   ├── funasr.html            #   FunASR speech recognition
│   ├── gae.html               #   Graph Autoencoder
│   ├── mario.html             #   Super Mario Bros game
│   ├── megatron_fp8.html      #   Megatron FP8 training
│   ├── monte_carlo_method.html #  Monte Carlo methods
│   └── rabitq.html            #   RaBitQ quantization
│
├── api/                       # Backend — Python (Flask / Vercel serverless)
│   ├── chat.py                #   Chat API — Kimi K2.5 agent loop + SSE streaming
│   ├── tools.py               #   10 agent tools (schemas + implementations)
│   ├── rag_utils.py           #   RAG retrieval over research_data.yaml
│   ├── chat_log.py            #   Conversation logging endpoint
│   ├── db_utils.py            #   Database utilities (Neon Postgres)
│   ├── scholar.py             #   Google Scholar citation fetcher
│   ├── sessions.py            #   Session management
│   ├── visitor.py             #   Visitor tracking & geo heatmap API
│   └── README.md              #   API documentation
│
├── assets/                    # Frontend shared assets
│   ├── css/wikipedia.css      #   Main stylesheet
│   ├── js/                    #   Client-side JavaScript
│   │   ├── github-stars.js    #     GitHub star counter
│   │   ├── navigation.js      #     Page navigation
│   │   ├── publications-loader.js  # Publications YAML loader
│   │   └── yaml-parser.js     #     YAML parser
│   ├── img/                   #   Images (profile pic, sprites, world map SVG)
│   └── audio/                 #   Audio files (Mario game sounds)
│
├── data/                      # Data files
│   ├── research_data.yaml     #   Publications + GitHub projects (single source of truth)
│   ├── citation_data.json     #   Citation map data (generated offline)
│   └── selected_publications.yaml  # Selected publications for homepage
│
├── docs/                      # Documentation
│   ├── DATABASE_SETUP.md      #   Neon Postgres setup guide
│   ├── RAG_DESIGN.md          #   RAG system architecture
│   └── YAML_USAGE.md          #   YAML data format reference
│
├── scripts/                   # Build & data generation scripts
│   ├── prerender-katex.js     #   KaTeX SSR pre-renderer (build step)
│   ├── generate_citation_data.py  # Citation map data generator
│   ├── screenshot.js          #   Playwright screenshot automation
│   └── take_screenshot.py     #   Python screenshot helper
│
├── tests/                     # Tests
│   ├── test_site.py           #   Site integration tests
│   ├── test_mario.py          #   Mario game tests
│   └── test*.js               #   JS game engine tests
│
├── .github/workflows/
│   └── static.yml             # GitHub Pages deployment (KaTeX SSR build → dist/)
│
├── vercel.json                # Vercel config (API routes, rewrites, CORS)
├── package.json               # Node.js dependencies (KaTeX)
├── requirements.txt           # Python dependencies
├── schema.sql                 # Database schema
└── .gitignore
```

## AI Agent Chat System

The chat page (`pages/chat.html`) is a full-featured AI agent powered by **Kimi K2.5** (Moonshot AI) with function calling, real-time streaming, and a Claude Code-inspired dark terminal UI.

### Architecture

```
User → chat.html (SSE) → /api/chat (Flask) → Kimi K2.5 API (Moonshot)
                                    ↕
                              Agent Tool Loop
                          (up to 10 rounds per query)
                                    ↕
                    ┌─────────────────────────────────┐
                    │  search_publications             │
                    │  fetch_webpage (trafilatura)      │
                    │  search_github_repo (GitHub API)  │
                    │  list_github_repos                │
                    │  get_citation_stats               │
                    │  read_site_page                   │
                    │  get_pinned_repos (GraphQL)       │
                    │  search_site_pages                │
                    │  get_repo_contributors            │
                    └─────────────────────────────────┘
```

### Backend (`api/chat.py`)

- **Model**: Kimi K2.5 via OpenAI-compatible SDK (`https://api.moonshot.cn/v1`)
- **Agent loop**: Function calling with up to 10 tool rounds per query
- **Streaming**: SSE (Server-Sent Events) with distinct event types:
  - `reasoning_start/delta/end` — K2.5 thinking process (token-by-token)
  - `message_delta` — final response content
  - `tool_call` / `tool_result` — tool invocation and results
  - `thinking` — status updates
  - `done` — completion signal
- **RAG**: Lightweight retrieval from `research_data.yaml` prepended to system prompt
- **Rate limit handling**: Automatic retry with `Retry-After` parsing for 429 errors
- **Context compression**: Automatic conversation summarization when context limit is reached — older messages are LLM-summarized to free token budget
- **max_tokens**: 131072 (128K context window)

### Frontend (`pages/chat.html`)

- **Claude Code UI**: Deep dark theme (`#0d1117`), monospace font (JetBrains Mono), terminal-style `>` prompt
- **Streaming rendering**: marked.js + highlight.js for real-time Markdown
- **Word-level blurIn animation**: Each new word fades in with `opacity:0 + blur(4px) → opacity:1 + blur(0)` (280ms ease-out)
- **Token drip system**: SSE tokens are buffered and rendered at a steady 60fps rate with adaptive acceleration to prevent backlog
- **Collapsible panels**: Tool calls show as `● Tool Name` with expandable IN/OUT blocks; thinking blocks show as `⟐ Thinking...`
- **Pulsing dot cursor**: Animated `●` indicator during streaming

### Agent Tools

| Tool | Description |
|---|---|
| `search_publications` | Search Xiang An's papers by keyword from `research_data.yaml` |
| `fetch_webpage` | Fetch and extract text from any URL via trafilatura |
| `search_github_repo` | Read files / list directories in a GitHub repo via API |
| `list_github_repos` | List public repos for a GitHub user/org |
| `get_citation_stats` | Citation statistics with geographic breakdown |
| `read_site_page` | Read HTML pages from this website |
| `get_pinned_repos` | Get GitHub user's pinned repos via GraphQL API |
| `search_site_pages` | Search all site pages (blogs, visualizations) by keyword |
| `get_repo_contributors` | Get repo contributor list with commit counts |

### SSE Event Protocol

```
reasoning_start  → Create collapsible thinking block
reasoning_delta  → Stream thinking content (Markdown rendered, blurIn animated)
reasoning_end    → Collapse thinking block
message_delta    → Stream response (Markdown rendered, blurIn animated)
tool_call        → Show tool invocation panel
tool_result      → Fill tool result into panel
thinking         → Status bar update
done             → Finalize, flush all buffers
```

## Deployment

### Hybrid: GitHub Pages + Vercel API (Recommended)

- **GitHub Pages** (`anxiangsir.github.io`) serves all static pages
- **Vercel** serves the Python Chat API + database endpoints
- The frontend auto-detects its host and routes API calls to the Vercel deployment cross-origin
- CORS configured in `vercel.json`

### Vercel Setup

1. Import the repository at [vercel.com/new](https://vercel.com/new)
2. Add environment variables:
   - `MOONSHOT_API_KEY` — Moonshot AI API key for Kimi K2.5
   - `POSTGRES_URL` (optional) — Neon Postgres connection string for conversation logging
3. Deploy — Vercel auto-detects `api/*.py` as Python serverless functions

### GitHub Pages (Static only)

The `static.yml` workflow runs `npm run build` (KaTeX SSR pre-rendering) and deploys `dist/` to GitHub Pages. The Chat API is **not available** under GitHub Pages alone.

## Local Development

```bash
# Clone
git clone https://github.com/anxiangsir/anxiangsir.github.io.git
cd anxiangsir.github.io

# Install dependencies
pip install -r requirements.txt
npm install

# Start the Chat API
export MOONSHOT_API_KEY="sk-xxx"
python api/chat.py          # Runs on http://localhost:5000

# Start the static file server
python -m http.server 8000  # Open http://localhost:8000

# (Optional) Build KaTeX SSR for math pages
npm run build
python -m http.server 8000 --directory dist
```

### Proxy Notes

External network access on internal servers requires:

```bash
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889
export no_proxy=127.0.0.1,localhost
```

## KaTeX SSR Build

Math-heavy pages (`areal.html`, `yarn.html`, `diffusion_models.html`) are pre-rendered at build time into static KaTeX HTML — zero runtime math JS on the deployed site.

The build copies the repo into `dist/`, pre-renders LaTeX in HTML and JS i18n strings, removes runtime KaTeX scripts, and localizes CSS/fonts to `dist/assets/vendor/katex/`.

## RAG System

The chat assistant uses lightweight RAG retrieval from `data/research_data.yaml` (the single source of truth for all publications and GitHub projects). Relevant entries are prepended to the system prompt before each LLM call. See [docs/RAG_DESIGN.md](docs/RAG_DESIGN.md) for architecture details.

## Citation World Map

The homepage includes an interactive Citation World Map showing the geographic distribution of citing authors.

- Data generated offline via `scripts/generate_citation_data.py` (Semantic Scholar API → geocoding → `data/citation_data.json`)
- Warm orange color scale on `assets/img/world-map.min.svg`

```bash
# Regenerate citation data (~5-10 min, rate-limited by S2 API)
pip install requests geopy pycountry tqdm
python scripts/generate_citation_data.py
```

## Database Setup

For conversation logging with Neon Postgres, see [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md).

## Architecture Notes

- `index.html` stays at root — GitHub Pages serves from `/` directly
- Non-index pages live in `pages/` — old URLs preserved via Vercel rewrites
- `api/` stays at root — Vercel serverless convention
- All internal links use absolute paths (`/pages/`, `/assets/`, `/data/`)
- `chat.html`, `llava_onevision2.html`, `partial_fc.html`, `video_codec.html`, `verl_grpo.html` use inline CSS/JS (tightly coupled to DOM)
- Bilingual pages (`index.html`, `video_codec.html`, `chat.html`) use `data-lang` attributes with a shared toggle pattern
