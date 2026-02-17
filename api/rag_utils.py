"""
RAG (Retrieval-Augmented Generation) utility module.

Provides lightweight keyword-based retrieval over a local knowledge base
of publications and GitHub projects.  No external vector-DB or embedding
model is required — designed for Vercel serverless cold-start constraints.
"""

import json
import math
import os
import re
from collections import Counter

_KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
_knowledge_base = None
_MEDIA_KEYWORDS = "media news 媒体 新闻 报道"


def _load_knowledge_base():
    """Load and cache the knowledge base from JSON."""
    global _knowledge_base
    if _knowledge_base is not None:
        return _knowledge_base

    with open(_KB_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    docs = []
    for doc in data.get("documents", []):
        # Build a single searchable string per document
        parts = [
            doc.get("title", ""),
            doc.get("authors", ""),
            doc.get("venue", ""),
            doc.get("summary", ""),
            doc.get("description", ""),
            doc.get("name", ""),
            doc.get("role", ""),
        ]
        keywords = doc.get("keywords", [])
        if keywords:
            parts.append(" ".join(keywords))

        media_links = doc.get("media_links", [])
        if media_links:
            parts.append(" ".join(ml.get("name", "") for ml in media_links))
            parts.append(_MEDIA_KEYWORDS)

        searchable = " ".join(p for p in parts if p).lower()
        docs.append({**doc, "_searchable": searchable})

    _knowledge_base = docs
    return _knowledge_base


# ── simple tokeniser ─────────────────────────────────────────────────
_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should can could may might must and or but if in "
    "on at to for of with by from as into about between through after "
    "before during without within along across behind beyond near "
    "what which who whom whose where when how that this these those "
    "i me my we our you your he him his she her it its they them their "
    "的 了 在 是 我 他 她 它 们 这 那 个 和 与 或 但 如果 因为 所以 也 都 就 "
    "请问 什么 哪个 怎么 如何 可以 能 会 要 想 "
    "".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.UNICODE)

# Chinese → English translation map for common research terms
_ZH_EN_MAP = {
    "人脸": "face",
    "识别": "recognition",
    "训练": "training",
    "检索": "retrieval",
    "图像": "image",
    "多模态": "multimodal",
    "视觉": "vision",
    "表征": "representation",
    "学习": "learning",
    "开源": "open source",
    "论文": "paper",
    "聚类": "cluster",
    "判别": "discrimination",
    "大模型": "large model",
    "编码器": "encoder",
    "文档": "document",
    "视频": "video",
    "蒸馏": "distillation",
    "预训练": "pretraining",
    "嵌入": "embedding",
    "对齐": "alignment",
    "生成": "generation",
    "皮肤": "skin",
    "项目": "project",
    "数据集": "dataset",
    "媒体": "media news",
    "传播": "media news",
    "新闻": "news media",
    "报道": "media news coverage",
}


def _tokenize(text):
    """Return a list of meaningful tokens from *text*.

    Chinese tokens are expanded to English equivalents so they can match
    the primarily English knowledge base.
    """
    raw = _TOKEN_RE.findall(text.lower())
    expanded = []
    for t in raw:
        if t in _STOP_WORDS:
            continue
        expanded.append(t)
        # If it's a Chinese token, also add English translations
        if re.fullmatch(r"[\u4e00-\u9fff]+", t):
            # Direct lookup first (O(1))
            if t in _ZH_EN_MAP:
                expanded.extend(_ZH_EN_MAP[t].split())
            else:
                # Substring matching for compound Chinese terms
                for zh, en in _ZH_EN_MAP.items():
                    if zh in t:
                        expanded.extend(en.split())
    return expanded


# ── BM25-lite scoring ────────────────────────────────────────────────
_K1 = 1.2
_B = 0.75


def _score_bm25(query_tokens, doc_searchable, avg_dl, n_docs, df_map):
    """Compute a simplified BM25 score for one document."""
    doc_tokens = _TOKEN_RE.findall(doc_searchable)
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for qt in query_tokens:
        f = tf.get(qt, 0)
        if f == 0:
            continue
        df = df_map.get(qt, 0)
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
        numerator = f * (_K1 + 1)
        denominator = f + _K1 * (1 - _B + _B * dl / max(avg_dl, 1))
        score += idf * numerator / denominator
    return score


# ── public API ────────────────────────────────────────────────────────
def search(query, top_k=3, min_score=0.5):
    """Return the *top_k* most relevant knowledge-base documents for *query*.

    Each result is a dict with the original document fields plus a
    ``_score`` key.
    """
    docs = _load_knowledge_base()
    if not docs:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Pre-compute document frequencies and average doc length
    n_docs = len(docs)
    all_lengths = []
    df_map = Counter()
    for d in docs:
        tokens = _TOKEN_RE.findall(d["_searchable"])
        unique_tokens = set(tokens)
        all_lengths.append(len(tokens))
        for t in unique_tokens:
            df_map[t] += 1
    avg_dl = sum(all_lengths) / max(n_docs, 1)

    scored = []
    for d in docs:
        s = _score_bm25(query_tokens, d["_searchable"], avg_dl, n_docs, df_map)
        if s >= min_score:
            scored.append({**d, "_score": s})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_k]


def format_context(results):
    """Format retrieved documents into a context string for the LLM."""
    if not results:
        return ""

    sections = []
    for r in results:
        doc_type = r.get("type", "")
        if doc_type == "publication":
            title = r.get("title", "")
            venue = r.get("venue", "")
            paper_url = r.get("paper_url", "")
            code_url = r.get("code_url", "")
            summary = r.get("summary", "")
            authors = r.get("authors", "")
            lines = [f"**{title}**"]
            if authors:
                lines.append(f"Authors: {authors}")
            if venue:
                lines.append(f"Venue: {venue}")
            if paper_url:
                lines.append(f"Paper: {paper_url}")
            if code_url:
                lines.append(f"Code: {code_url}")
            if summary:
                lines.append(f"Summary: {summary}")
            media_links = r.get("media_links", [])
            if media_links:
                ml_parts = [
                    f"[{ml['name']}]({ml['url']})"
                    for ml in media_links
                    if ml.get("name") and ml.get("url")
                ]
                if ml_parts:
                    lines.append(f"Media coverage: {', '.join(ml_parts)}")
            sections.append("\n".join(lines))

        elif doc_type == "github_project":
            name = r.get("name", "")
            url = r.get("url", "")
            role = r.get("role", "")
            desc = r.get("description", "")
            stars = r.get("stars", "")
            lines = [f"**{name}**"]
            if url:
                lines.append(f"URL: {url}")
            if stars:
                lines.append(f"Stars: {stars}")
            if role:
                lines.append(f"Role: {role}")
            if desc:
                lines.append(f"Description: {desc}")
            sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)
