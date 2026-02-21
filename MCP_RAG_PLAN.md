# RAG + PDF 论文接入 MCP 服务 — 完整设计方案

> **目标**：让你的个人网站 Chat 助手不仅能检索 `knowledge_base.json` 中的结构化元数据，还能**深入检索论文 PDF 全文内容**，并通过 **MCP (Model Context Protocol)** 服务将此能力暴露给各类 AI 客户端（如 Claude Desktop、Cursor、Continue 等）。

---

## 目录

1. [现状分析](#1-现状分析)
2. [目标架构总览](#2-目标架构总览)
3. [Phase 1：PDF 解析与分块](#3-phase-1pdf-解析与分块)
4. [Phase 2：向量化检索升级](#4-phase-2向量化检索升级)
5. [Phase 3：MCP Server 实现](#5-phase-3mcp-server-实现)
6. [Phase 4：与现有 Chat API 集成](#6-phase-4与现有-chat-api-集成)
7. [Phase 5：部署与运维](#7-phase-5部署与运维)
8. [文件结构规划](#8-文件结构规划)
9. [技术选型对比](#9-技术选型对比)
10. [里程碑与时间线](#10-里程碑与时间线)

---

## 1. 现状分析

### 当前 RAG 系统

| 组件 | 现状 |
|------|------|
| **知识源** | `api/knowledge_base.json`（26 个文档：22 篇论文元数据 + 4 个项目） |
| **检索算法** | BM25 关键词匹配（`api/rag_utils.py`） |
| **数据粒度** | 论文级别（title/authors/venue/summary），**无全文内容** |
| **跨语言** | 中英文翻译字典 `_ZH_EN_MAP` |
| **部署** | Vercel Serverless（Python Flask） |
| **MCP 支持** | ❌ 无 |

### 痛点

1. **信息深度不足**：只有论文摘要和一句话 summary，无法回答论文方法细节、实验数据等深层问题
2. **检索精度有限**：BM25 是关键词匹配，无法理解语义相似性
3. **无 MCP 接口**：外部 AI 工具无法直接访问你的论文知识库
4. **PDF 未利用**：论文 PDF 文件完全未被索引

---

## 2. 目标架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI 客户端层                                    │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ 网站Chat │  │ Claude   │  │ Cursor   │  │ 其他MCP客户端     │    │
│  │ (现有)   │  │ Desktop  │  │   IDE    │  │ (Continue等)     │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────────┘    │
│       │              │              │               │                │
│       │         ┌────┴──────────────┴───────────────┘                │
│       │         │  MCP Protocol (JSON-RPC over stdio/SSE)           │
│       │         │                                                    │
└───────┼─────────┼────────────────────────────────────────────────────┘
        │         │
        ▼         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         服务层                                       │
│                                                                     │
│  ┌──────────────────┐      ┌──────────────────────────────┐         │
│  │ /api/chat (现有) │      │ MCP Server (新增)             │         │
│  │ Flask + DashScope │      │ - search_papers tool         │         │
│  │ + RAG context     │◄────►│ - get_paper_detail tool      │         │
│  └────────┬─────────┘      │ - list_papers tool           │         │
│           │                 │ - search_by_topic tool       │         │
│           │                 └──────────┬───────────────────┘         │
│           │                            │                             │
│           ▼                            ▼                             │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              RAG Engine (升级版)                          │        │
│  │                                                         │        │
│  │  ┌─────────────┐    ┌──────────────┐    ┌───────────┐  │        │
│  │  │ BM25 检索   │    │ 向量检索      │    │ 混合检索   │  │        │
│  │  │ (保留现有)  │    │ (新增)        │    │ (组合)     │  │        │
│  │  └──────┬──────┘    └──────┬───────┘    └─────┬─────┘  │        │
│  │         └──────────────────┼───────────────────┘        │        │
│  │                            │                             │        │
│  └────────────────────────────┼─────────────────────────────┘        │
│                               │                                      │
└───────────────────────────────┼──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         数据层                                       │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────┐   ┌───────────────────┐   │
│  │ knowledge_base   │   │ PDF 全文分块  │   │ 向量数据库         │   │
│  │ .json (现有)     │   │ (新增)        │   │ (新增)            │   │
│  └──────────────────┘   └──────────────┘   └───────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    PDF 文件存储                                │   │
│  │   papers/                                                     │   │
│  │   ├── partial_fc_cvpr2022.pdf                                │   │
│  │   ├── unicom_iclr2023.pdf                                    │   │
│  │   ├── mlcd_eccv2024.pdf                                      │   │
│  │   └── ...                                                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1：PDF 解析与分块

### 3.1 目标

将论文 PDF 文件解析为可检索的文本块（chunks）。

### 3.2 PDF 存储结构

```
papers/
├── partial_fc_cvpr2022.pdf
├── partial_fc_iccvw2021.pdf
├── unicom_iclr2023.pdf
├── mlcd_eccv2024.pdf
├── onevision_encoder_2026.pdf
├── llava_onevision_1_5.pdf
└── ...
```

### 3.3 PDF 解析工具选型

| 工具 | 优势 | 劣势 | 推荐场景 |
|------|------|------|---------|
| **PyMuPDF (fitz)** | 快速、轻量、保留布局 | 表格提取一般 | ✅ 首选：学术论文文本提取 |
| **pdfplumber** | 表格提取优秀 | 速度较慢 | 含大量表格的论文 |
| **marker** | AI 驱动，LaTeX 公式支持好 | 依赖重 | 需要精确公式转换 |
| **Docling (IBM)** | 结构化解析、图表理解 | 较新 | 企业级文档处理 |

**推荐方案**：使用 **PyMuPDF** 作为主解析器，轻量且适合 serverless。

### 3.4 文本分块策略

```python
# 分块参数建议
CHUNK_SIZE = 512       # 每个 chunk 的 token 数
CHUNK_OVERLAP = 64     # 相邻 chunk 的重叠 token 数
```

**分块层次结构**：

```
论文 PDF
 ├── 元数据块 (title, authors, abstract)     ← 来自 knowledge_base.json
 ├── Section: Introduction                    ← 段落级分块
 │    ├── chunk_001 (512 tokens)
 │    └── chunk_002 (512 tokens, 64 overlap)
 ├── Section: Method
 │    ├── chunk_003
 │    ├── chunk_004
 │    └── chunk_005
 ├── Section: Experiments
 │    ├── chunk_006
 │    └── chunk_007
 └── Section: Conclusion
      └── chunk_008
```

### 3.5 实现代码示意

```python
# api/pdf_parser.py (新增文件)

import fitz  # PyMuPDF
import os
import json
import re

def extract_text_from_pdf(pdf_path: str) -> str:
    """从 PDF 文件中提取纯文本。"""
    with fitz.open(pdf_path) as doc:
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
    return text


def split_into_chunks(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """将文本分割为带重叠的 chunks。"""
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")
    
    words = text.split()
    chunks = []
    start = 0
    
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({
            "text": chunk_text,
            "start_idx": start,
            "end_idx": end,
        })
        start += chunk_size - overlap
    
    return chunks


def process_papers_directory(papers_dir: str, output_path: str):
    """处理整个 papers/ 目录，生成分块索引。"""
    all_chunks = []
    
    for filename in os.listdir(papers_dir):
        if not filename.endswith(".pdf"):
            continue
        
        pdf_path = os.path.join(papers_dir, filename)
        paper_id = filename.replace(".pdf", "")
        
        # 提取文本
        text = extract_text_from_pdf(pdf_path)
        
        # 分块
        chunks = split_into_chunks(text)
        
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "id": f"{paper_id}_chunk_{i:03d}",
                "paper_id": paper_id,
                "source_file": filename,
                "chunk_index": i,
                "text": chunk["text"],
            })
    
    # 保存分块数据
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"chunks": all_chunks}, f, ensure_ascii=False, indent=2)
    
    print(f"Processed {len(all_chunks)} chunks from papers/")
```

---

## 4. Phase 2：向量化检索升级

### 4.1 目标

在保留现有 BM25 检索的基础上，增加语义向量检索，实现**混合检索 (Hybrid Retrieval)**。

### 4.2 Embedding 模型选型

| 模型 | 维度 | 多语言 | 部署方式 | 推荐 |
|------|------|--------|---------|------|
| **DashScope text-embedding-v3** | 1024 | ✅ 中英 | API 调用 | ✅ 首选（你已有 DashScope API Key） |
| OpenAI text-embedding-3-small | 1536 | ✅ | API 调用 | 备选 |
| BGE-M3 (BAAI) | 1024 | ✅ | 本地 / API | 开源自建 |
| sentence-transformers | 384-768 | 部分 | 本地 | 轻量但效果一般 |

**推荐**：使用 **DashScope text-embedding-v3**，与你现有的 Qwen LLM 在同一生态，无需新增 API Key。

### 4.3 向量存储选型

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **JSON 文件 + NumPy** | 零依赖、简单 | 不适合大规模 | ✅ 首选（< 500 chunks） |
| Chroma | 轻量、Python 原生 | 需持久化 | 中等规模 |
| Neon pgvector | 复用现有 Postgres | 需要扩展 | ✅ 备选（已有 Neon DB） |
| Qdrant Cloud | 高性能、有免费 tier | 外部依赖 | 大规模 |

**推荐方案**：

- **首选**：JSON 文件 + NumPy 余弦相似度（你的论文约 20-30 篇，分块后约 200-500 chunks，完全够用）
- **备选**：利用你现有的 Neon Postgres 添加 pgvector 扩展

### 4.4 混合检索实现

```python
# api/hybrid_search.py (新增文件)

import numpy as np
from rag_utils import search as bm25_search
from vector_store import vector_search

def hybrid_search(query: str, top_k: int = 5, bm25_weight: float = 0.3, vector_weight: float = 0.7):
    """
    混合检索：BM25 关键词匹配 + 语义向量检索。
    
    Args:
        query: 用户查询
        top_k: 返回结果数
        bm25_weight: BM25 分数权重
        vector_weight: 向量检索分数权重
    """
    # 1. BM25 检索（现有 knowledge_base.json 元数据）
    bm25_results = bm25_search(query, top_k=top_k * 2)
    
    # 2. 向量检索（PDF 全文 chunks）
    vector_results = vector_search(query, top_k=top_k * 2)
    
    # 3. 分数归一化 + 加权融合
    all_results = {}
    
    for r in bm25_results:
        doc_id = r.get("id", r.get("paper_id", ""))
        all_results[doc_id] = {
            "doc": r,
            "bm25_score": r.get("_score", 0),
            "vector_score": 0,
        }
    
    for r in vector_results:
        doc_id = r.get("id", r.get("paper_id", ""))
        if doc_id in all_results:
            all_results[doc_id]["vector_score"] = r.get("_score", 0)
        else:
            all_results[doc_id] = {
                "doc": r,
                "bm25_score": 0,
                "vector_score": r.get("_score", 0),
            }
    
    # 4. 计算混合分数
    for doc_id, data in all_results.items():
        data["hybrid_score"] = (
            bm25_weight * data["bm25_score"] +
            vector_weight * data["vector_score"]
        )
    
    # 5. 排序并返回 top_k
    sorted_results = sorted(
        all_results.values(),
        key=lambda x: x["hybrid_score"],
        reverse=True,
    )
    
    return sorted_results[:top_k]
```

---

## 5. Phase 3：MCP Server 实现

### 5.1 什么是 MCP？

**MCP (Model Context Protocol)** 是 Anthropic 开源的一个协议，定义了 AI 模型与外部数据源/工具之间的标准化通信方式。通过 MCP Server，你的论文知识库可以被任何支持 MCP 的客户端（Claude Desktop、Cursor、Continue 等）直接访问。

### 5.2 MCP Server Tools 设计

```
MCP Server: "paper-rag-server"
│
├── Tool: search_papers
│   ├── 输入: { query: string, top_k?: number }
│   ├── 功能: 混合检索论文（BM25 + 向量）
│   └── 输出: 匹配的论文列表 + 相关文本片段
│
├── Tool: get_paper_detail
│   ├── 输入: { paper_id: string }
│   ├── 功能: 获取特定论文的完整信息
│   └── 输出: 论文元数据 + 全文 chunks
│
├── Tool: list_papers
│   ├── 输入: { year?: number, venue?: string }
│   ├── 功能: 列出所有论文，支持按年份/会议筛选
│   └── 输出: 论文列表
│
├── Tool: search_by_topic
│   ├── 输入: { topic: string }
│   ├── 功能: 按研究主题检索
│   └── 输出: 相关论文及其关键章节
│
├── Resource: papers://list
│   ├── 功能: 暴露论文列表作为静态资源
│   └── 输出: 所有论文的结构化元数据
│
└── Resource: papers://{paper_id}/content
    ├── 功能: 暴露特定论文内容
    └── 输出: 论文全文（分段）
```

### 5.3 MCP Server 实现代码

```python
# mcp_server/server.py (新增文件)

import asyncio
import json
import os
import sys

# 确保可以导入 api/ 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

import rag_utils

# ─── 初始化 MCP Server ───────────────────────────────────
app = Server("paper-rag-server")


# ─── 定义 Tools ──────────────────────────────────────────
@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_papers",
            description="搜索安翔的学术论文和研究项目。支持中英文查询。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，例如 'Partial FC face recognition' 或 '人脸识别训练'",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_paper_detail",
            description="获取特定论文的详细信息，包括全文内容片段。",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "论文 ID，例如 'pub_partial_fc_cvpr'",
                    },
                },
                "required": ["paper_id"],
            },
        ),
        Tool(
            name="list_papers",
            description="列出所有论文，支持按年份和会议筛选。",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "筛选年份，例如 2024",
                    },
                    "venue": {
                        "type": "string",
                        "description": "筛选会议/期刊，例如 'CVPR' 或 'ECCV'",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_papers":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        results = rag_utils.search(query, top_k=top_k)
        formatted = rag_utils.format_context(results)
        return [TextContent(type="text", text=formatted or "未找到相关论文。")]
    
    elif name == "get_paper_detail":
        paper_id = arguments.get("paper_id", "")
        docs = rag_utils._load_knowledge_base()
        doc = next((d for d in docs if d.get("id") == paper_id), None)
        if doc:
            return [TextContent(type="text", text=json.dumps(doc, ensure_ascii=False, indent=2))]
        return [TextContent(type="text", text=f"未找到论文: {paper_id}")]
    
    elif name == "list_papers":
        docs = rag_utils._load_knowledge_base()
        year = arguments.get("year")
        venue = arguments.get("venue", "").lower()
        
        filtered = []
        for d in docs:
            if d.get("type") != "publication":
                continue
            if year and d.get("year") != year:
                continue
            if venue and venue not in d.get("venue", "").lower():
                continue
            filtered.append({
                "id": d.get("id"),
                "title": d.get("title"),
                "venue": d.get("venue"),
                "year": d.get("year"),
            })
        
        return [TextContent(type="text", text=json.dumps(filtered, ensure_ascii=False, indent=2))]
    
    return [TextContent(type="text", text=f"未知工具: {name}")]


# ─── 定义 Resources ──────────────────────────────────────
@app.list_resources()
async def list_resources():
    return [
        Resource(
            uri="papers://list",
            name="论文列表",
            description="安翔的所有学术论文和研究项目",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str):
    if uri == "papers://list":
        docs = rag_utils._load_knowledge_base()
        papers = [
            {"id": d.get("id"), "title": d.get("title", d.get("name")), "type": d.get("type")}
            for d in docs
        ]
        return json.dumps(papers, ensure_ascii=False, indent=2)
    return "Resource not found"


# ─── 启动 ────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
```

### 5.4 MCP 客户端配置

客户端连接 MCP Server 的配置文件：

```json
// Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json
// Cursor: .cursor/mcp.json
{
  "mcpServers": {
    "paper-rag": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "cwd": "/path/to/anxiangsir.github.io"
    }
  }
}
```

也可以使用 SSE（HTTP）传输方式实现远程访问：

```python
# mcp_server/server_sse.py — 用于远程部署
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount

sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1])

starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)
```

---

## 6. Phase 4：与现有 Chat API 集成

### 6.1 修改 `api/chat.py`

升级现有 chat API，使用混合检索替代纯 BM25：

```python
# api/chat.py 修改要点

# 原来:
# results = rag_utils.search(last_user_msg, top_k=3)

# 改为:
from hybrid_search import hybrid_search

results = hybrid_search(last_user_msg, top_k=5)
rag_context = format_hybrid_results(results)
```

### 6.2 保持向后兼容

- 现有的 `/api/chat` REST API 继续工作
- BM25 检索作为 fallback（向量服务不可用时自动降级）
- `knowledge_base.json` 继续用于结构化元数据

---

## 7. Phase 5：部署与运维

### 7.1 部署方案

```
┌─────────────────────────────────────────────────┐
│                 部署架构                          │
│                                                  │
│  GitHub Pages (静态)                              │
│  ├── index.html                                  │
│  ├── publications.html                           │
│  └── assets/                                     │
│                                                  │
│  Vercel (Serverless)                             │
│  ├── /api/chat      ← 升级：混合检索             │
│  ├── /api/chat-log  ← 保持不变                   │
│  └── /api/mcp-sse   ← 新增：MCP SSE endpoint    │
│                                                  │
│  本地 / 独立服务器                                │
│  └── MCP stdio server ← 新增：本地 MCP 开发用    │
│                                                  │
│  Neon Postgres                                   │
│  ├── chat_sessions   ← 现有                      │
│  ├── chat_messages   ← 现有                      │
│  └── paper_embeddings ← 新增（可选 pgvector）     │
└─────────────────────────────────────────────────┘
```

### 7.2 依赖安装

```bash
# requirements.txt 新增
PyMuPDF>=1.24.0          # PDF 解析
numpy>=1.24.0            # 向量计算
mcp>=1.0.0               # MCP SDK
```

### 7.3 PDF 预处理脚本

```bash
# 一次性预处理脚本（开发时运行）
python scripts/build_index.py \
    --papers-dir papers/ \
    --output api/paper_chunks.json \
    --embeddings api/paper_embeddings.npy
```

### 7.4 环境变量

```bash
# .env 新增
DASHSCOPE_API_KEY=xxx    # 已有 — 用于 Embedding + LLM
EMBEDDING_MODEL=text-embedding-v3  # DashScope Embedding 模型
```

---

## 8. 文件结构规划

```
anxiangsir.github.io/
├── api/                          # Vercel Serverless Functions
│   ├── chat.py                   # [修改] 集成混合检索
│   ├── rag_utils.py              # [保留] BM25 检索
│   ├── knowledge_base.json       # [保留] 结构化元数据
│   ├── pdf_parser.py             # [新增] PDF 解析器
│   ├── vector_store.py           # [新增] 向量存储与检索
│   ├── hybrid_search.py          # [新增] 混合检索引擎
│   ├── paper_chunks.json         # [新增] PDF 分块数据（预生成）
│   ├── paper_embeddings.npy      # [新增] 向量嵌入（预生成）
│   ├── db_utils.py               # [保留]
│   ├── chat_log.py               # [保留]
│   ├── sessions.py               # [保留]
│   └── scholar.py                # [保留]
│
├── mcp_server/                   # [新增] MCP Server
│   ├── server.py                 # MCP stdio server（本地开发）
│   ├── server_sse.py             # MCP SSE server（远程部署）
│   └── __init__.py
│
├── papers/                       # [新增] 论文 PDF 存储
│   ├── partial_fc_cvpr2022.pdf
│   ├── unicom_iclr2023.pdf
│   └── ...
│
├── scripts/                      # [新增] 工具脚本
│   ├── build_index.py            # PDF 预处理 + 向量化
│   └── validate_index.py         # 索引验证
│
├── _data/
│   ├── publications.yaml         # [保留] 论文元数据
│   └── selected_publications.yaml
│
├── index.html                    # [保留]
├── publications.html             # [保留]
├── vercel.json                   # [修改] 添加 MCP SSE 路由
├── requirements.txt              # [修改] 添加新依赖
├── RAG_DESIGN.md                 # [保留]
├── MCP_RAG_PLAN.md               # [新增] 本文档
└── ...
```

---

## 9. 技术选型对比

### 选型 A：轻量方案（推荐起步）

| 组件 | 选择 | 理由 |
|------|------|------|
| PDF 解析 | PyMuPDF | 轻量、快速、零依赖 |
| Embedding | DashScope text-embedding-v3 | 复用已有 API Key |
| 向量存储 | JSON + NumPy | 零依赖，适合小规模 |
| 检索策略 | BM25 + 向量混合 | 兼顾精确匹配和语义理解 |
| MCP 传输 | stdio (本地) + SSE (远程) | 兼顾开发和部署 |

### 选型 B：企业级方案（可选升级）

| 组件 | 选择 | 理由 |
|------|------|------|
| PDF 解析 | Docling (IBM) | 结构化解析、图表理解 |
| Embedding | BGE-M3 自建 | 完全自控 |
| 向量存储 | Neon pgvector | 复用现有数据库 |
| 检索策略 | ColBERT / RAPTOR | 更先进的检索方法 |
| MCP 传输 | Streamable HTTP | MCP 最新标准 |

---

## 10. 里程碑与时间线

| 阶段 | 时间 | 交付物 | 优先级 |
|------|------|--------|--------|
| **Phase 1** | 第 1 周 | PDF 解析 + 分块 + `paper_chunks.json` | 🔴 高 |
| **Phase 2** | 第 2 周 | 向量化 + 混合检索 + `hybrid_search.py` | 🔴 高 |
| **Phase 3** | 第 3 周 | MCP Server (stdio) + 3 个 Tools | 🟡 中 |
| **Phase 4** | 第 4 周 | 集成到现有 Chat API + SSE 部署 | 🟡 中 |
| **Phase 5** | 第 5 周 | 生产部署 + 监控 + 文档 | 🟢 低 |

### 快速验证步骤

如果你想快速验证效果，可以按以下顺序执行最小可行版本（MVP）：

1. 在 `papers/` 放入 2-3 篇代表性论文 PDF
2. 运行 `scripts/build_index.py` 生成分块数据
3. 在本地启动 MCP Server (`python mcp_server/server.py`)
4. 在 Claude Desktop 中配置连接，验证 `search_papers` tool
5. 确认效果后再部署到 Vercel

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
- [DashScope Embedding API](https://help.aliyun.com/zh/model-studio/text-embedding)
- [BM25 算法详解](./RAG_DESIGN.md)（本仓库现有文档）
