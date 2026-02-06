# Chat API Documentation

## Overview

Python Flask chat service powered by Alibaba Cloud DashScope (Qwen model).

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Set the `DASHSCOPE_API_KEY` environment variable:

```bash
export DASHSCOPE_API_KEY="sk-xxx"
```

For GitHub Actions, add `DASHSCOPE_API_KEY` as a **Repository secret**:
- Go to **Settings → Secrets and variables → Actions → New repository secret**
- Name: `DASHSCOPE_API_KEY`
- Value: your API key from [阿里云百炼](https://help.aliyun.com/model-studio/getting-started/models)

### 3. Run the Service

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
- Use environment variables or Repository secrets for `DASHSCOPE_API_KEY`.
- Consider adding rate limiting for production use.
