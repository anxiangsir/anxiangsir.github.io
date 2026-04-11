# Chat API Documentation

## Overview

Python Flask chat service powered by GitHub Models (OpenAI-compatible endpoint), with integrated Vercel Postgres database for conversation logging and RAG retrieval over local publications & GitHub projects.

## API Endpoints

### 1. POST /api/chat - Chat with AI Assistant

Main chat endpoint. Sends conversation history to the LLM and returns a reply.

### 2. POST /api/chat-log - Save Conversation Log

Saves a conversation message to the database.

### 3. GET /api/chat-log - Retrieve Conversation History

Retrieves conversation history for a specific session.

### 4. GET /api/sessions - List All Sessions

Lists all conversation sessions with statistics.

### 5. POST /api/visitor - Record Visitor

Records an anonymized visitor hit with geo-location.

### 6. GET /api/visitor - Visitor Heatmap Data

Returns aggregated visitor data by country for the visitor map.

See [DATABASE_SETUP.md](../docs/DATABASE_SETUP.md) for detailed database documentation.

## Deployment

### Vercel (Recommended)

Vercel automatically detects `api/*.py` files as Python serverless functions.

1. Import the repository at [vercel.com/new](https://vercel.com/new).
2. Add environment variables in **Settings → Environment Variables**:
   - `GITHUB_TOKEN` — a GitHub Personal Access Token with access to GitHub Models
   - `CHAT_MODEL` (optional) — model name, defaults to `openai/gpt-4.1`
   - `POSTGRES_URL` (optional) — Neon Postgres connection string for conversation logging
3. Deploy — the `/api/chat` endpoint is available immediately.

> **Important:** GitHub Actions **Repository secrets** are only available during CI/CD workflow runs. They are **not** passed to the Vercel runtime. You must set environment variables in **Vercel's** Settings.

### Local

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configure API Key

Set the `GITHUB_TOKEN` environment variable:

```bash
export GITHUB_TOKEN="ghp_xxx"
```

Get a token from [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens). The token needs access to GitHub Models.

Optionally set a custom model:

```bash
export CHAT_MODEL="openai/gpt-4.1"
```

### Run the Service

```bash
python api/chat.py
```

The service starts at `http://localhost:5000`. Set a custom port with:

```bash
PORT=8080 python api/chat.py
```

## API Endpoint

**URL:** `/api/chat`
**Method:** `POST`
**Content-Type:** `application/json`

### Request Body

Supports full conversation history:

```json
{
  "messages": [
    {"role": "user", "content": "你是谁？"},
    {"role": "assistant", "content": "我是安翔的 AI 助手。"},
    {"role": "user", "content": "介绍一下他的研究"}
  ]
}
```

Or a single message (backward-compatible):

```json
{
  "message": "你是谁？"
}
```

### Success Response

```json
{
  "reply": "AI的回复"
}
```

### Error Response

```json
{
  "error": "错误信息",
  "reply": "抱歉，服务暂时不可用。"
}
```

## Frontend Integration

The chat page at `pages/chat.html` calls `POST /api/chat` with full conversation history.
When the page is served from GitHub Pages (`anxiangsir.github.io`), it calls the Vercel-hosted API cross-origin.
Update the `API_BASE` constant in `pages/chat.html` if your Vercel production URL changes.

## Security

- **Never** commit API keys to the repository.
- Use Vercel Environment Variables or local environment variables for `GITHUB_TOKEN`.
- Consider adding rate limiting for production use.
