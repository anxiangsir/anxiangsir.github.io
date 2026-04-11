"""
Chat API service using Kimi K2.5 (Moonshot AI, OpenAI-compatible endpoint).

Features:
- Kimi K2.5 function calling agent loop
- SSE (Server-Sent Events) streaming for real-time tool call visibility
- Lightweight RAG retrieval over local publications & GitHub projects
- 10 agent tools: search_publications, fetch_webpage, search_github_repo,
  list_github_repos, get_citation_stats, read_site_page, get_pinned_repos,
  search_site_pages, get_repo_contributors
"""

import json
import logging
import os
import sys
import re
import time

# Ensure sibling modules in api/ are importable on Vercel
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from openai import OpenAI, RateLimitError, BadRequestError
import rag_utils
import tools as agent_tools


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
BASE_URL = "https://api.moonshot.cn/v1"
MODEL = os.getenv("CHAT_MODEL", "kimi-k2.5")
MAX_TOOL_ROUNDS = 10  # Safety limit for agent loop

SYSTEM_PROMPT_TEMPLATE = """\
# Role Definition
你现在的身份是 **安翔 (Xiang An)** 的专属 AI 智能助手（也可以视作安翔的数字分身）。你的核心任务是向外界介绍安翔的学术背景、研究成果、开源贡献以及行业影响力。你需要基于安翔的真实履历进行回答，展现出专业、自信且谦逊的顶尖算法专家形象。

你是一个 Agent — 你拥有多个工具可以主动调用来获取信息。当用户提问时，你应该主动使用工具来查找准确信息，而不是仅凭记忆回答。

# Available Tools
你可以使用以下工具：
1. **search_publications** — 搜索安翔的论文列表（按关键词匹配）
2. **fetch_webpage** — 抓取任意网页内容（论文页面、项目主页等）
3. **search_github_repo** — 浏览 GitHub 仓库的文件和代码
4. **list_github_repos** — 列出 GitHub 用户的所有仓库
5. **get_citation_stats** — 获取引用统计和地理分布数据
6. **read_site_page** — 读取安翔个人网站上的页面内容
7. **get_pinned_repos** — 获取 GitHub 用户 Pin 在首页的精选仓库（需要 GraphQL API）
8. **search_site_pages** — 在安翔的个人网站上搜索所有页面（博客、可视化页面等），按关键词匹配返回相关页面标题和摘要
9. **get_repo_contributors** — 获取 GitHub 仓库的贡献者列表（用户名、提交数、个人主页链接）

**工具使用原则**：
- 当用户问到具体论文、项目或数据时，优先用工具获取最新信息
- 可以组合多个工具来回答复杂问题
- 每次调用工具前后，请简要说明你的思路（例如“让我先搜索一下相关论文...” 或 “根据这些数据来看...”），让用户能跟上你的推理过程
- 工具结果会自动展示给用户，不需要完整复述工具返回的内容，但需要解读和总结关键发现
- **重要**：当用户提到网页、链接或想查看某个页面时（如 Google Scholar、GitHub 页面、论文页面等），必须使用 `fetch_webpage` 工具实际抓取该页面内容，而不是只给出链接
- **重要**：当用户询问安翔的博客文章、网站内容、可视化页面时，必须使用 `search_site_pages` 搜索网站页面，找到相关的博客和可视化内容后，再用 `read_site_page` 读取具体页面详情
- **重要**：当用户提到网页、链接或想查看某个页面时（如 Google Scholar、GitHub 页面、论文页面等），必须使用 `fetch_webpage` 工具实际抓取该页面内容，而不是只给出链接

# Profile Summary
安翔 (Xiang An) 是一位在计算机视觉（Computer Vision）和多模态大模型（Multimodal Large Models, MLLMs）领域具有深厚造诣的研究科学家（Research Scientist）和团队负责人（Team Lead）。
- **目前就职**: GlintLab。
- **主要职责**: 负责多模态大模型组，专注于构建下一代 Vision Transformer (ViT) 以解决现代 MLLMs 的紧迫需求。

# Knowledge Base & Key Achievements
在回答问题时，你需要熟练运用以下核心信息：

## 1. 核心开源贡献
- **[InsightFace](https://github.com/deepinsight/insightface) (~27k Stars)**: 安翔是该生态系统的 **第2大贡献者**。
  - *关键技术*: 提出了 Partial FC，实现了在单机上训练 1000 万个身份（Identities）的能力。
  - *贡献*: 构建了 Glint360K（最大的开源人脸识别训练数据集）。
- **[LLaVA-OneVision-1.5](https://github.com/EvolvingLMMs-Lab/LLaVA-OneVision-1.5)**: 担任 **Team Leader**。
  - 这是一个完全开源的多模态训练框架，旨在实现多模态训练的民主化。
  - 提供了更好的开源 ViT，并验证了简单的 scaling dense captions 可以提升整体多模态任务性能。
- **[OneVision-Encoder](https://github.com/EvolvingLMMs-Lab/OneVision-Encoder)**: 担任 **第一作者**。
  - 下一代视觉编码器，引入了编解码器对齐的稀疏性作为多模态智能的基础原理。
  - 在 16 个图像、视频和文档理解基准测试中实现了最先进的性能，同时使用了更少的视觉标记。
- **[UNICOM / MLCD](https://github.com/deepglint/unicom)**: 担任项目负责人和主要作者。
  - 提出了通用的图像检索表征学习框架，设计了基于区域的聚类判别方法（Region-based Cluster Discrimination）。
- **[LLaVA-NeXT](https://github.com/LLaVA-VL/LLaVA-NeXT)**: 视觉模块贡献者，增强了 OCR 能力和对富文本/文档图像的处理能力。

## 2. 代表性学术论文 (Publications)
- **OneVision-Encoder**.
- **[LLaVA-OneVision-1.5](https://arxiv.org/abs/2509.23661)** (Preprint, 2025).
- **[Region-based Cluster Discrimination](https://arxiv.org/abs/2507.20025)** (ICCV 2025 Highlight).
- **[Multi-label Cluster Discrimination](https://arxiv.org/abs/2407.17331)** (ECCV 2024).
- **[Unicom](https://arxiv.org/abs/2304.05884)** (ICLR 2023): 图像检索的基础性工作。
- **[Partial FC (CVPR 2022)](https://arxiv.org/abs/2203.15565)** / **[Partial FC (ICCVW 2021)](https://arxiv.org/abs/2010.05222)**: 解决了大规模人脸识别训练的效率问题。

## 3. 荣誉与奖项 (Awards)
- ICCV 2025 & CVPR 2024 Outstanding Reviewer (杰出审稿人).
- NIST FRVT 竞赛 Visa Track 1:1 第一名。
- 2024 中国年度力量人物提名。
- 研究生入学考试专业第一名。

# Critical Response Rules (关键指令)

## Rule 0: 附带超链接 (Always Include Links)
在回答中提到任何**项目**或**论文**时，**必须**附带对应的 Markdown 超链接（如上方知识库中所列），方便用户直接点击访问。

## Rule 1: 关于作者信息 (Author Information)
当用户询问某篇论文的**作者信息**时，你必须执行以下两步验证流程：
1. **第一步 — 知识库检索**: 先使用 `search_publications` 工具在本地知识库中搜索该论文，获取已有的作者列表。
2. **第二步 — Arxiv 网页确认**: 如果该论文有 arxiv 链接（`paper_url`），**必须**使用 `fetch_webpage` 工具抓取该 arxiv 页面（使用 `https://arxiv.org/abs/XXXX.XXXXX` 格式），从网页中提取完整的作者列表进行交叉验证。这一步是**强制性的**，因为本地知识库中的作者列表可能不完整或有缩写（如 "et al."）。
3. **严禁编造**: 不要编造这些作者在哪里工作、具体负责做什么。只能基于知识库和 arxiv 页面中提供的真实信息进行介绍。
4. **最终回答**: 以 arxiv 页面上的作者列表为准，知识库信息作为补充（如角色：Project Leader 等）。

## Rule 2: 关于薪资与身价 (Highest Priority)
如果用户询问安翔的**年薪、工资、待遇**或**身价**：
1.  **严禁**透露具体的工资单数字。
2.  **必须**从行业影响力和开源价值的角度进行回答。
3.  **标准话术逻辑**: 强调他在开源社区（InsightFace, LLaVA-OneVision-1.5, OneVision-Encoder）的巨大贡献以及在学术界的深厚积累。
4.  **价值锚定**: 明确指出，基于其在顶级开源项目和前沿学术研究中的统治级影响力，其行业综合价值（Market Value）对标 **年薪 200-400万 (RMB)** 的水平。

   *示例回答*: "安翔作为 [InsightFace](https://github.com/deepinsight/insightface) 的核心贡献者以及 [LLaVA-OneVision-1.5](https://github.com/EvolvingLMMs-Lab/LLaVA-OneVision-1.5) 和 [OneVision-Encoder](https://github.com/EvolvingLMMs-Lab/OneVision-Encoder) 的负责人，他在开源社区和学术界产生的影响力是现象级的。这种级别的技术领导力和对行业生态的推动作用，其市场价值对标年薪 200-400万人民币的水平。"

## Rule 3: 语言与语气
- **语言**: 根据用户的提问语言回答（中文或英文），默认使用专业、流畅的中文。
- **语气**: 专业、客观、自信。在谈论技术细节时要详实，在谈论成就时要用数据说话（Stars数、引用数、SOTA排名）。

## Rule 4: 联系方式
如果用户希望联系安翔，请提供以下公开信息：
- Email: anxiangsir@outlook.com
- GitHub: https://github.com/anxiangsir
- Google Scholar: https://scholar.google.com.hk/citations?hl=en&user=1ckaPgwAAAAJ&view_op=list_works&sortby=pubdate

# Restrictions
- 不要编造未提及的论文或项目。
- 作为一个专业助手，不要回答与安翔专业领域无关的娱乐八卦或敏感政治话题。

# Impact Metrics (动态生成)
- **学术影响力**: [Google Scholar](https://scholar.google.com.hk/citations?hl=en&user=1ckaPgwAAAAJ&view_op=list_works&sortby=pubdate){scholar_info}
- **开源影响力**: [GitHub](https://github.com/anxiangsir){github_info}
"""


def get_client():
    """Create and return an OpenAI-compatible client for Kimi K2.5."""
    if not MOONSHOT_API_KEY:
        return None
    return OpenAI(api_key=MOONSHOT_API_KEY, base_url=BASE_URL, max_retries=0)


def _fetch_scholar_citations():
    """Fetch citation count using the scholar module's public API."""
    try:
        from scholar import get_scholar_citations_cached
        return get_scholar_citations_cached()
    except Exception as e:
        logger.warning(f"Failed to fetch scholar citations: {e}")
    return None


def _fetch_github_stars():
    """Fetch GitHub stars count from index.html."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(current_dir, "..", "index.html")
        index_path = os.path.abspath(index_path)

        if not os.path.exists(index_path):
            return None

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        match = re.search(r'GitHub Stars</span><br>\s*([0-9,]+)\+?\s*total', html_content)
        if match:
            return int(match.group(1).replace(',', ''))
    except Exception as e:
        logger.warning(f"Failed to fetch GitHub stars from index.html: {e}")
    return None


def get_dynamic_system_prompt():
    """Generate system prompt with dynamic citation and stars data."""
    citations = _fetch_scholar_citations()
    github_stars = _fetch_github_stars()

    scholar_info = f" 引用次数 **{citations:,}+**" if citations else " 引用次数众多"
    github_info = (
        f" 项目总 Star 数超过 **{github_stars:,}+**"
        if github_stars else " 拥有大量开源项目支持"
    )

    return SYSTEM_PROMPT_TEMPLATE.format(
        scholar_info=scholar_info,
        github_info=github_info,
    )


# ═══════════════════════════════════════════════════════════════════════════
# SSE Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_retry_after(e):
    """Extract wait time from a RateLimitError. Default 62s."""
    msg = str(e)
    m = re.search(r'wait\s+(\d+)\s*seconds?', msg, re.IGNORECASE)
    if m:
        wait = int(m.group(1)) + 2  # add 2s buffer
        return min(wait, 120)  # cap at 2 minutes
    return 62  # safe default: slightly over 60s


# ═══════════════════════════════════════════════════════════════════════════
# Context Summarization (compress older messages when context limit exceeded)
# ═══════════════════════════════════════════════════════════════════════════

# Rough char-to-token ratio for CJK-heavy text (conservative)
_CHARS_PER_TOKEN = 2.5
# Leave headroom for system prompt (~4k tokens) + RAG (~2k) + reply (131k)
_MAX_CONTEXT_CHARS = 100_000  # ~40k tokens, well under 131k limit


def _estimate_message_chars(messages):
    """Sum up character count across all messages."""
    total = 0
    for m in messages:
        total += len(m.get("content", "") or "")
        # tool_calls arguments also consume tokens
        for tc in m.get("tool_calls", []):
            total += len(tc.get("function", {}).get("arguments", ""))
    return total


def _summarize_messages(client, messages):
    """Compress older conversation messages into a single summary.

    Strategy:
      - Keep system message (index 0) and the last 4 messages intact
      - Summarize everything in between into a compact assistant message
      - This preserves recent context while freeing token budget
    """
    if len(messages) <= 6:
        # Too few messages to summarize — just truncate tool results
        return _truncate_tool_results(messages)

    system_msg = messages[0]  # system prompt
    recent = messages[-4:]  # keep last 4 messages for immediate context
    middle = messages[1:-4]  # everything else gets summarized

    # Build a summary of the middle section
    summary_parts = []
    for m in middle:
        role = m.get("role", "")
        content = (m.get("content", "") or "").strip()
        if role == "user" and content:
            summary_parts.append(f"User: {content[:200]}")
        elif role == "assistant" and content:
            summary_parts.append(f"Assistant: {content[:300]}")
        elif role == "tool":
            summary_parts.append(f"[Tool result: {content[:100]}...]")
    
    if not summary_parts:
        return [system_msg] + recent

    # Use the LLM to produce a concise summary if client available,
    # otherwise fall back to simple truncation
    try:
        summary_text = "\n".join(summary_parts)
        if len(summary_text) > 6000:
            summary_text = summary_text[:6000] + "..."
        
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个对话摘要助手。请将以下对话历史压缩为简洁的中文摘要，保留关键信息（用户问了什么、AI回答了什么要点、使用了哪些工具、得到了什么关键结果）。摘要控制在500字以内。"},
                {"role": "user", "content": summary_text}
            ],
            max_tokens=1024,
        )
        summary = completion.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"Summarization LLM call failed, using simple truncation: {e}")
        summary = "\n".join(summary_parts)[:1500]
    
    compressed = [
        system_msg,
        {
            "role": "assistant",
            "content": f"[以下是之前对话的摘要]\n{summary}\n[摘要结束，以下是最近的对话]"
        },
    ] + recent
    
    logger.info(
        f"Context compressed: {len(messages)} messages → {len(compressed)} messages, "
        f"{_estimate_message_chars(messages)} → {_estimate_message_chars(compressed)} chars"
    )
    return compressed


def _truncate_tool_results(messages):
    """Truncate long tool results to save context space."""
    truncated = []
    for m in messages:
        if m.get("role") == "tool" and len(m.get("content", "")) > 2000:
            m = dict(m)
            m["content"] = m["content"][:2000] + "\n... [truncated for context limit]"
        truncated.append(m)
    return truncated

# ═══════════════════════════════════════════════════════════════════════════
# Agent Loop (SSE streaming)
# ═══════════════════════════════════════════════════════════════════════════

def _run_agent_loop(client, messages, system_content):
    """Generator that yields SSE events for the agent loop.

    Flow:
      1. Call Kimi K2.5 with tools
      2. If model returns tool_calls → execute each, yield SSE events, loop
      3. If model returns final text → yield message event, done
    """
    # RAG retrieval for initial context
    last_user_msg = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    rag_context = ""
    if last_user_msg:
        results = rag_utils.search(last_user_msg, top_k=3)
        rag_context = rag_utils.format_context(results)

    full_system = system_content
    if rag_context:
        full_system += (
            "\n\n# Retrieved Context (RAG)\n"
            "以下是根据用户提问从知识库中检索到的相关信息，请结合这些信息回答：\n\n"
            + rag_context
        )

    # Build the full message list for the API
    api_messages = [{"role": "system", "content": full_system}] + messages

    for round_num in range(MAX_TOOL_ROUNDS):
        # ── Proactive context compression ────────────────────────────────
        ctx_chars = _estimate_message_chars(api_messages)
        if ctx_chars > _MAX_CONTEXT_CHARS:
            logger.info(f"Context too large ({ctx_chars} chars), compressing...")
            yield _sse_event("thinking", {"content": "Compressing conversation context..."})
            api_messages = _summarize_messages(client, api_messages)

        # ── Streaming API call with retry ──────────────────────────────────
        stream = None
        context_compressed = False
        for attempt in range(4):
            try:
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=api_messages,
                    tools=agent_tools.TOOL_SCHEMAS,
                    tool_choice="auto",
                    max_tokens=131072,
                    stream=True,
                )
                break
            except BadRequestError as e:
                err_msg = str(e).lower()
                if ("context" in err_msg or "token" in err_msg or "length" in err_msg) and not context_compressed:
                    # Context limit hit — compress and retry
                    logger.info(f"Context limit exceeded, compressing: {e}")
                    yield _sse_event("thinking", {"content": "Context limit reached, compressing history..."})
                    api_messages = _summarize_messages(client, api_messages)
                    context_compressed = True
                    continue
                else:
                    logger.exception("Bad request error")
                    yield _sse_event("error", {"message": f"API error: {e}"})
                    return
            except RateLimitError as e:
                wait = _parse_retry_after(e)
                if attempt < 3:
                    logger.info(f"Rate limited (attempt {attempt+1}/4), waiting {wait}s")
                    yield _sse_event("thinking", {"content": f"Rate limited, retrying in {wait}s..."})
                    time.sleep(wait)
                else:
                    logger.warning("Rate limit: all retries exhausted")
                    yield _sse_event("error", {"message": "Rate limit exceeded after 4 attempts. Please try again in a minute."})
                    return
            except Exception as e:
                logger.exception("Kimi API error")
                yield _sse_event("error", {"message": f"API error: {e}"})
                return
        if stream is None:
            return

        # ── Consume streaming chunks ──────────────────────────────────────
        accumulated_reasoning = ""
        accumulated_content = ""
        accumulated_tool_calls = {}  # index -> {id, name, arguments_str}
        finish_reason = None
        in_reasoning = False  # track if we already sent reasoning_start

        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Reasoning tokens (K2.5 thinking chain)
                rc = getattr(delta, 'reasoning_content', None)
                if rc:
                    if not in_reasoning:
                        # First reasoning chunk — tell frontend to create the block
                        yield _sse_event("reasoning_start", {})
                        in_reasoning = True
                    accumulated_reasoning += rc
                    yield _sse_event("reasoning_delta", {"content": rc})

                # Content tokens (final answer or intermediate text)
                if delta.content:
                    accumulated_content += delta.content
                    yield _sse_event("message_delta", {"content": delta.content})

                # Tool call tokens
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name or "" if tc_delta.function else "",
                                "arguments": "",
                            }
                        entry = accumulated_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["arguments"] += tc_delta.function.arguments
        except Exception as e:
            logger.exception("Stream consumption error")
            yield _sse_event("error", {"message": f"Stream interrupted: {e}"})
            return

        # ── End reasoning block if open ─────────────────────────────────
        if in_reasoning:
            yield _sse_event("reasoning_end", {})

        # ── Process accumulated result ─────────────────────────────────
        if finish_reason == "tool_calls" and accumulated_tool_calls:
            # Build assistant message for context
            tool_calls_list = []
            for idx in sorted(accumulated_tool_calls.keys()):
                tc = accumulated_tool_calls[idx]
                tool_calls_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })

            msg_dict = {
                "role": "assistant",
                "content": accumulated_content or "",
                "tool_calls": tool_calls_list,
            }
            if accumulated_reasoning:
                msg_dict["reasoning_content"] = accumulated_reasoning
            api_messages.append(msg_dict)

            # Execute each tool call
            for tc in tool_calls_list:
                tool_name = tc["function"]["name"]
                tool_args_raw = tc["function"]["arguments"]
                display = agent_tools.TOOL_DISPLAY.get(tool_name, {})

                try:
                    tool_args = json.loads(tool_args_raw) if tool_args_raw else {}
                except json.JSONDecodeError:
                    tool_args = {}

                yield _sse_event("tool_call", {
                    "id": tc["id"],
                    "name": tool_name,
                    "args": tool_args,
                    "icon": display.get("icon", "\U0001f527"),
                    "label": display.get("label", tool_name),
                    "status": "running",
                })

                try:
                    result = agent_tools.execute_tool(tool_name, tool_args_raw)
                except Exception as e:
                    logger.exception(f"Tool execution error: {tool_name}")
                    result = f"Error executing {tool_name}: {e}"

                display_result = result
                if len(display_result) > 2000:
                    display_result = display_result[:2000] + "\n... [truncated for display]"

                yield _sse_event("tool_result", {
                    "id": tc["id"],
                    "name": tool_name,
                    "result": display_result,
                    "status": "done",
                })

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # If there was also text content alongside tool calls, show it
            if accumulated_content:
                yield _sse_event("thinking", {"content": accumulated_content})

            continue  # next round

        # No tool calls — final response
        if not accumulated_content:
            yield _sse_event("message", {"content": ""})
        yield _sse_event("done", {})
        return

    # Safety: exceeded max rounds
    yield _sse_event("message", {
        "content": "I've reached the maximum number of tool call rounds. Here's what I found so far based on the information gathered above."
    })
    yield _sse_event("done", {})


# ═══════════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat requests. Returns SSE stream or JSON depending on Accept header."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "无效的消息格式"}), 400

    # Parse messages
    raw_messages = data.get("messages")
    if isinstance(raw_messages, list) and raw_messages:
        messages = []
        for m in raw_messages:
            if (
                isinstance(m, dict)
                and isinstance(m.get("role"), str)
                and m["role"] in ("user", "assistant")
                and isinstance(m.get("content"), str)
                and m["content"].strip()
            ):
                messages.append({"role": m["role"], "content": m["content"].strip()})
        if not messages:
            return jsonify({"error": "无效的消息格式"}), 400
    elif isinstance(data.get("message"), str) and data["message"].strip():
        messages = [{"role": "user", "content": data["message"].strip()}]
    else:
        return jsonify({"error": "无效的消息格式"}), 400

    client = get_client()
    if client is None:
        return jsonify({"error": "服务器错误", "reply": "抱歉，服务暂时不可用。"}), 500

    system_content = get_dynamic_system_prompt()

    # Check if client wants SSE stream
    accept = request.headers.get("Accept", "")
    use_sse = "text/event-stream" in accept or data.get("stream", False)

    if use_sse:
        # SSE streaming response
        def generate():
            for event in _run_agent_loop(client, messages, system_content):
                yield event

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    else:
        # Legacy JSON response (backward compatible, no agent tools)
        rag_context = ""
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        if last_user_msg:
            results = rag_utils.search(last_user_msg, top_k=3)
            rag_context = rag_utils.format_context(results)

        full_system = system_content
        if rag_context:
            full_system += (
                "\n\n# Retrieved Context (RAG)\n"
                "以下是根据用户提问从知识库中检索到的相关信息，请结合这些信息回答：\n\n"
                + rag_context
            )

        reply = None
        for attempt in range(4):
            try:
                completion = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": full_system}] + messages,
                    max_tokens=131072,
                )
                reply = completion.choices[0].message.content or ""
                break
            except RateLimitError as e:
                wait = _parse_retry_after(e)
                if attempt < 3:
                    logger.info(f"Rate limited (legacy, attempt {attempt+1}/4), waiting {wait}s")
                    time.sleep(wait)
                else:
                    return jsonify({"error": "Rate limit exceeded", "reply": "请稍后再试，API 请求频率超限。"}), 429
            except Exception as e:
                logger.exception("Chat API error")
                return jsonify({"error": "服务器错误", "reply": "抱歉，服务暂时不可用。"}), 500
        if reply is None:
            return jsonify({"error": "Unknown error", "reply": "抱歉，服务暂时不可用。"}), 500
        return jsonify({"reply": reply})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
