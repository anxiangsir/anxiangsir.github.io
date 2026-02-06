# Chat API Documentation

## Overview

Python Flask chat service powered by Alibaba Cloud DashScope (Qwen model).

## Deployment

### Vercel (Recommended)

Vercel automatically detects `api/chat.py` as a Python serverless function.

1. Import the repository at [vercel.com/new](https://vercel.com/new).
2. Add the `DASHSCOPE_API_KEY` environment variable in **Settings → Environment Variables**.
3. Deploy — the `/api/chat` endpoint is available immediately.

> **Important:** GitHub Actions **Repository secrets** are only available during CI/CD workflow runs. They are **not** passed to the Vercel runtime. You must set `DASHSCOPE_API_KEY` in **Vercel's** Environment Variables.

### Local

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configure API Key

Set the `DASHSCOPE_API_KEY` environment variable:

```bash
export DASHSCOPE_API_KEY="sk-xxx"
```

Get your API key from [阿里云百炼](https://help.aliyun.com/model-studio/getting-started/models).

For Vercel deployments, set `DASHSCOPE_API_KEY` in **Vercel → Settings → Environment Variables**.

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

The `index.html` chat interface calls `POST /api/chat` automatically.
Update the `CHAT_API_URL` constant in `index.html` if your service runs on a different host.

## Security

- **Never** commit API keys to the repository.
- Use Vercel Environment Variables or local environment variables for `DASHSCOPE_API_KEY`.
- Consider adding rate limiting for production use.
