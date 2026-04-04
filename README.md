# [Xiang An's Personal Homepage](https://anxiangsir.github.io/)

## Features

- Responsive personal homepage with research profile
- AI-powered chat assistant using Alibaba Cloud DashScope (Qwen model)
- Automatic conversation logging to Neon Postgres database
- Interactive visualizations: PartialFC training pipeline, LLaVA-OneVision2 codec animation
- Citation World Map: citing-author geographic distribution from Semantic Scholar (offline-generated)
- Hybrid deployment: GitHub Pages (static) + Vercel (API + Database)

## Project Structure

```
anxiangsir.github.io/
├── index.html                 # Homepage (Wikipedia-style layout)
│
├── pages/                     # HTML pages (non-index)
│   ├── partial_fc.html        #   PartialFC interactive visualization
│   ├── llava_onevision2.html  #   LLaVA-OneVision2 codec animation
│   ├── blog.html              #   Blog index
│   ├── publications.html      #   Publications page
│   └── yarn.html              #   YaRN visualization
│
├── api/                       # Backend — Vercel serverless functions (Python)
│   ├── chat.py                #   Chat API endpoint
│   ├── chat_log.py            #   Chat logging endpoint
│   ├── db_utils.py            #   Database utilities
│   ├── knowledge_base.json    #   RAG knowledge base
│   ├── rag_utils.py           #   RAG retrieval utilities
│   ├── scholar.py             #   Google Scholar API
│   ├── sessions.py            #   Session management
│   └── README.md              #   API documentation
│
├── assets/                    # Frontend shared assets
│   ├── css/                   #   Stylesheets (wikipedia.css)
│   ├── js/                    #   Client-side JavaScript
│   │   ├── github-stars.js    #     GitHub star counter
│   │   ├── navigation.js      #     Page navigation
│   │   ├── publications-loader.js  # Publications YAML loader
│   │   └── yaml-parser.js     #     YAML parser
│   ├── img/                   #   Images (profile pic, sprites)
│   ├── audio/                 #   Audio files
│   └── snd/                   #   Sound effects
│
├── data/                      # Data files
│   ├── citation_data.json     #   Citation map data (generated offline)
│   ├── publications.yaml      #   Full publications list
│   └── selected_publications.yaml  # Selected publications
│
├── docs/                      # Documentation & screenshots
│   ├── DATABASE_SETUP.md      #   Neon Postgres setup guide
│   ├── RAG_DESIGN.md          #   RAG system architecture
│   ├── YAML_USAGE.md          #   YAML data format reference
│   └── screenshot*.png        #   Site screenshots
│
├── scripts/                   # Development & build scripts
│   ├── generate_citation_data.py  # Citation map data generator (headless)
│   ├── screenshot.js          #   Playwright screenshot automation
│   ├── take_screenshot.py     #   Python screenshot helper
│   ├── mcp-client.js          #   MCP client utility
│   └── test-mcp.js            #   MCP connection test
│
├── tests/                     # Test files
│   ├── test.js                #   Mario game engine tests
│   ├── test2.js               #   Mario game engine v2
│   ├── test_sim2.js           #   Simulation tests
│   └── test_mario.py          #   Mario integration test
│
├── .github/workflows/
│   └── static.yml             # GitHub Pages deployment workflow
│
├── vercel.json                # Vercel config (API routes, rewrites, CORS)
├── package.json               # Node.js dependencies
├── requirements.txt           # Python dependencies
├── schema.sql                 # Database schema
└── .gitignore
```

### Architecture Notes

- **`index.html` stays at root** — GitHub Pages serves from `/` directly.
- **Non-index HTML pages live in `pages/`** — old URLs (`/blog.html`, `/partial_fc.html`, etc.) are preserved via Vercel rewrites in `vercel.json`.
- **`api/` stays at root** — Vercel's serverless convention requires this.
- **All internal links use absolute paths** (`/pages/blog.html`, `/assets/js/...`, `/data/...`) so pages work regardless of their directory depth.
- **`llava_onevision2.html`** and **`partial_fc.html`** use inline `<style>` and `<script>` — their CSS/JS is tightly coupled to the DOM pool rendering system and not suitable for extraction.

## Deployment

### Vercel (Recommended — supports Chat API + Database)

The site includes a Python-based Chat API (`api/chat.py`) and database logging features that require a serverless runtime and Postgres database. [Vercel](https://vercel.com/) is recommended because it serves both the static pages and Python API endpoints, while [Neon](https://neon.tech/) provides the serverless Postgres database.

1. **Import the repository** at [vercel.com/new](https://vercel.com/new).
2. **Add the environment variable** `DASHSCOPE_API_KEY` in **Settings → Environment Variables** with your API key from [阿里云百炼](https://help.aliyun.com/model-studio/getting-started/models).
3. **Create and connect Neon Postgres database** (optional, for conversation logging):
   - Create a database at [Neon Console](https://console.neon.tech/) (recommended) or via Vercel Storage
   - Add the `POSTGRES_URL` environment variable in **Settings → Environment Variables**
   - Follow the setup guide in [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md)
4. **Deploy** — Vercel automatically serves static files and the Python serverless functions.

> **Note:** GitHub Actions **Repository secrets** are only available during CI/CD workflow runs. They are **not** injected into the runtime environment of static sites or serverless functions. Use Vercel Environment Variables instead.

### GitHub Pages (Static only — Chat API unavailable)

The `static.yml` workflow now installs Node.js dependencies, runs the KaTeX pre-render build, and deploys the generated `dist/` directory to GitHub Pages. Because GitHub Pages serves only static files, the Chat API (`/api/chat`) is **not available** under this deployment method.

### Hybrid: GitHub Pages + Vercel API (Recommended)

When the site is visited at `https://anxiangsir.github.io/`, the frontend automatically detects that it is **not** running on Vercel and redirects Chat API calls to the Vercel deployment (`https://anxiangsir-github-anxiangsirs-projects.vercel.app/api/chat`).

This means:
- **Static pages** are served by GitHub Pages at `anxiangsir.github.io`.
- **Chat API** is served by Vercel's serverless function cross-origin.
- CORS headers in `vercel.json` allow requests from `anxiangsir.github.io`.

> **Tip:** If your Vercel production URL changes, update the `VERCEL_ORIGIN` constant in `index.html`.

## Local Development

1. **Clone the Repository**

   ```bash
   git clone https://github.com/anxiangsir/anxiangsir.github.io.git
   cd anxiangsir.github.io
   ```

2. **Start the Chat API (optional)**

   ```bash
   pip install -r requirements.txt
   export DASHSCOPE_API_KEY="sk-xxx"
   python api/chat.py
   ```

3. **Start a Local Server**

   ```bash
   python -m http.server 8000
   # or
   npx live-server
   ```

4. **Open** http://localhost:8000

### KaTeX SSR Build

Math-heavy pages are pre-rendered at build time into static KaTeX HTML so the deployed site has zero runtime math rendering JavaScript.

#### Pages Covered

- `pages/areal.html`
- `pages/yarn.html`
- `pages/diffusion_models.html`

#### What the build does

- copies the repository into `dist/`
- pre-renders LaTeX in both static HTML and JavaScript i18n strings
- removes runtime `katex.min.js`, `auto-render.min.js`, and `renderMathInElement(...)`
- localizes KaTeX CSS/fonts to `dist/assets/vendor/katex/`
- keeps source HTML files in `pages/` unchanged

#### Build locally

```bash
npm install
npm run build

# Preview the built site
python -m http.server 8000 --directory dist
```

#### Proxy notes for this server environment

External network access requires the internal proxy:

```bash
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889
```

For local preview, bypass the proxy for localhost requests:

```bash
export no_proxy=127.0.0.1,localhost
python -m http.server 8000 --directory dist
```

### Deployment & Maintenance (Simple Overview)

This site is currently managed as a **static GitHub Pages deployment with a build step**.

#### How deployment works

1. Source files live in the repository root (`index.html`, `pages/`, `assets/`, `data/`, etc.).
2. On every push to `main`, GitHub Actions runs `.github/workflows/static.yml`.
3. The workflow:
   - installs Node dependencies with `npm ci`
   - runs `npm run build`
   - generates a built site into `dist/`
   - deploys `dist/` to GitHub Pages

#### What is generated vs. what is edited

- **Edit by hand:** source files in `pages/`, `index.html`, `assets/`, `data/`, scripts, README, workflow files
- **Generated by build:** `dist/`

For math-heavy pages, the build step pre-renders KaTeX into static HTML, strips runtime math JS, and copies local KaTeX assets into `dist/assets/vendor/katex/`.

#### How to update the site safely

Typical workflow:

```bash
# edit source files
npm run build
python -m http.server 8000 --directory dist
```

Then open the built page locally and verify it before committing.

#### What to maintain

- **Content changes** → edit source HTML / JSON / assets
- **Math rendering changes** → update `scripts/prerender-katex.js`
- **Deployment behavior** → update `.github/workflows/static.yml`
- **Dependencies** → update `package.json` / `package-lock.json`

#### Current deployment split

- **GitHub Pages** serves the static frontend
- **Vercel** is only needed if you want the Python Chat API runtime

So for normal blog/page updates, the main thing to remember is:

> edit source → build to `dist/` → GitHub Actions deploys `dist/`

## RAG System

The chat assistant uses a lightweight RAG (Retrieval-Augmented Generation) system to retrieve relevant publications and GitHub projects from a local knowledge base before calling the LLM. See [docs/RAG_DESIGN.md](docs/RAG_DESIGN.md) for architecture details.

## Database Setup

For setting up conversation logging with Neon Postgres, see [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md).

## Citation World Map

The homepage includes an interactive Citation World Map showing the geographic distribution of citing authors, generated offline from Semantic Scholar data.

### How It Works

1. `scripts/generate_citation_data.py` collects all citing papers via the Semantic Scholar API, then batch-looks up author affiliations
2. Affiliations are geocoded via `geopy` (Nominatim) to determine country locations
3. Results are aggregated by country and written to `data/citation_data.json`
4. The homepage JS reads this JSON and colors the SVG world map with warm orange tones

### Regenerating Citation Data

```bash
# Set proxy (required on internal servers)
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889

# Install dependencies
pip install requests geopy pycountry tqdm

# Generate data (~5-10 minutes, rate-limited by S2 API)
python scripts/generate_citation_data.py

# Output: data/citation_data.json
# Cache: scripts/.citation_cache/ (delete to force re-scrape)
```

### Configuration

- **S2 Author ID**: `2054941340` (hardcoded in `scripts/generate_citation_data.py`)
- **Google Scholar ID**: `1ckaPgwAAAAJ` (used for display link only)
- **Color scale**: Warm orange (`#fde8d0` → `#b35a1a`), distinct from the Visitor Map's blue tones
- **SVG**: Reuses `assets/img/world-map.min.svg` with ISO 3166-1 lowercase country code IDs
- **JSON schema**: `{scholar_id, s2_author_id, total_citations, total_countries, total_institutions, countries: {ISO_CODE: {name, count, institutions: [{name, count, lat, lng}]}}}`
