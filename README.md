# [Xiang An's Personal Homepage](https://anxiangsir.github.io/)

## Features

- Responsive personal homepage with research profile
- AI-powered chat assistant using Alibaba Cloud DashScope (Qwen model)
- Automatic conversation logging to Neon Postgres database
- Interactive visualizations: PartialFC training pipeline, LLaVA-OneVision2 codec animation
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
│   ├── yarn.html              #   YaRN visualization
│   └── blog/
│       └── partialfc.html     #   PartialFC explainer article
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

The `static.yml` workflow deploys the site to GitHub Pages. Because GitHub Pages serves only static files, the Chat API (`/api/chat`) is **not available** under this deployment method.

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

## RAG System

The chat assistant uses a lightweight RAG (Retrieval-Augmented Generation) system to retrieve relevant publications and GitHub projects from a local knowledge base before calling the LLM. See [docs/RAG_DESIGN.md](docs/RAG_DESIGN.md) for architecture details.

## Database Setup

For setting up conversation logging with Neon Postgres, see [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md).
