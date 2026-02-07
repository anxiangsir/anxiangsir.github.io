# [Xiang An's Personal Homepage](https://anxiangsir.github.io/)

## Features

- 📱 Responsive personal homepage with research profile
- 🤖 AI-powered chat assistant using Alibaba Cloud DashScope (Qwen model)
- 💾 Automatic conversation logging to Neon Postgres database
- 🔄 Hybrid deployment: GitHub Pages (static) + Vercel (API + Database)

## Deployment

### Vercel (Recommended — supports Chat API + Database)

The site includes a Python-based Chat API (`api/chat.py`) and database logging features that require a serverless runtime and Postgres database. [Vercel](https://vercel.com/) is recommended because it serves both the static pages and Python API endpoints, while [Neon](https://neon.tech/) provides the serverless Postgres database.

1. **Import the repository** at [vercel.com/new](https://vercel.com/new).
2. **Add the environment variable** `DASHSCOPE_API_KEY` in **Settings → Environment Variables** with your API key from [阿里云百炼](https://help.aliyun.com/model-studio/getting-started/models).
3. **Create and connect Neon Postgres database** (optional, for conversation logging):
   - Create a database at [Neon Console](https://console.neon.tech/) (recommended) or via Vercel Storage
   - Add the `POSTGRES_URL` environment variable in **Settings → Environment Variables**
   - Follow the setup guide in [DATABASE_SETUP.md](DATABASE_SETUP.md)
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

   Using Python's built-in HTTP server:

   ```bash
   # Python 3
   python -m http.server 8000
   ```

   Or using Node.js live-server (needs to be installed first):

   ```bash
   npm install -g live-server
   live-server
   ```

4. **Access the Website**

   Open http://localhost:8000 in your browser to view the website.

## RAG System

The chat assistant uses a lightweight RAG (Retrieval-Augmented Generation) system to retrieve relevant publications and GitHub projects from a local knowledge base before calling the LLM, enabling more accurate and detailed answers. For a detailed explanation of the architecture, BM25 scoring algorithm, and cross-language support, see [RAG_DESIGN.md](RAG_DESIGN.md).

## Database Setup

For setting up conversation logging with Neon Postgres, see [DATABASE_SETUP.md](DATABASE_SETUP.md).