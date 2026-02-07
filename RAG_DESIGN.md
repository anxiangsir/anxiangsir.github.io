# RAG 系统设计文档

> **RAG** = **R**etrieval-**A**ugmented **G**eneration（检索增强生成）

本文档详细解释本站 Chat 助手中 RAG 系统的原理、架构和实现细节。

---

## 目录

1. [什么是 RAG](#什么是-rag)
2. [整体架构](#整体架构)
3. [知识库（Knowledge Base）](#知识库knowledge-base)
4. [检索引擎原理](#检索引擎原理)
   - [分词（Tokenization）](#分词tokenization)
   - [停用词过滤](#停用词过滤)
   - [中英文跨语言支持](#中英文跨语言支持)
   - [BM25 评分算法](#bm25-评分算法)
5. [上下文注入（Context Injection）](#上下文注入context-injection)
6. [端到端数据流](#端到端数据流)
7. [设计取舍与优势](#设计取舍与优势)
8. [相关文件](#相关文件)

---

## 什么是 RAG

**RAG（Retrieval-Augmented Generation）** 是一种将**信息检索**与**大语言模型（LLM）生成**结合的技术范式：

```
传统 LLM:   用户问题 ──→ LLM ──→ 回答（仅依赖模型自身知识）

RAG:        用户问题 ──→ 检索相关文档 ──→ 文档 + 问题 ──→ LLM ──→ 回答
```

**核心思想**：在调用 LLM 之前，先从一个外部知识库中检索出与用户提问最相关的文档片段，然后将这些文档作为额外上下文一起发送给 LLM，让模型"有据可依"地生成回答。

**解决的问题**：
- LLM 的参数知识可能过时或不够具体
- 纯靠 System Prompt 硬编码的信息量有限
- RAG 让模型能够引用具体的论文数据、项目链接、作者信息等精确内容

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器 (index.html)                    │
│                                                                 │
│  conversationHistory[] ──→ POST /api/chat {messages: [...]}     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     api/chat.py (Flask)                         │
│                                                                 │
│  1. 解析消息，提取最新用户提问                                      │
│  2. ★ 调用 rag_utils.search() 检索知识库                          │
│  3. ★ 将检索结果注入 System Prompt                                │
│  4. 发送 [System Prompt + 检索上下文 + 对话历史] 到 DashScope       │
│  5. 返回 LLM 回复                                                │
└────────┬──────────────────────────────────┬─────────────────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────────┐          ┌────────────────────────┐
│  api/rag_utils.py   │          │  DashScope (Qwen)      │
│                     │          │  阿里云大模型 API         │
│  • 加载 knowledge   │          └────────────────────────┘
│    _base.json       │
│  • BM25 检索        │
│  • 格式化上下文      │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ knowledge_base.json │
│                     │
│ • 22 篇学术论文      │
│ • 4 个 GitHub 项目   │
└─────────────────────┘
```

---

## 知识库（Knowledge Base）

知识库存储在 `api/knowledge_base.json`，是一个 JSON 文件，包含两类文档：

### 论文文档（type: "publication"）

```json
{
  "id": "pub_partial_fc_cvpr",
  "type": "publication",
  "title": "Killing Two Birds with One Stone: Efficient and Robust Training ...",
  "authors": "Xiang An, Jiankang Deng, ...",
  "venue": "CVPR 2022",
  "year": 2022,
  "paper_url": "https://arxiv.org/abs/2203.15565",
  "code_url": "https://github.com/deepinsight/insightface/...",
  "summary": "This CVPR 2022 paper introduces Partial FC, ..."
}
```

### 项目文档（type: "github_project"）

```json
{
  "id": "project_insightface",
  "type": "github_project",
  "name": "InsightFace",
  "url": "https://github.com/deepinsight/insightface",
  "stars": "27k+",
  "role": "2nd largest contributor",
  "description": "State-of-the-art 2D and 3D face analysis toolbox. ...",
  "keywords": ["face recognition", "partial fc", "insightface", ...]
}
```

加载时，每个文档的所有文本字段（title, authors, venue, summary, description, keywords 等）被拼接为一个小写的 `_searchable` 字符串，用于后续检索匹配。

---

## 检索引擎原理

检索引擎实现在 `api/rag_utils.py`，核心流程：**分词 → 停用词过滤 → 跨语言扩展 → BM25 打分 → Top-K 返回**。

### 分词（Tokenization）

使用正则表达式提取 token：

```python
_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.UNICODE)
```

- 匹配连续的小写英文字母/数字，或连续的中文字符
- 例如 `"Partial FC training"` → `["partial", "fc", "training"]`
- 例如 `"人脸识别训练"` → `["人脸识别训练"]`（中文作为连续 token）

### 停用词过滤

过滤掉没有区分意义的常见词（英文 + 中文），例如：
- 英文: `a, the, is, are, in, on, for, ...`
- 中文: `的, 了, 在, 是, 请问, 什么, ...`

### 中英文跨语言支持

知识库内容主要是英文，但用户经常用中文提问。系统通过一个**中英翻译字典**解决这个问题：

```python
_ZH_EN_MAP = {
    "人脸": "face",
    "识别": "recognition",
    "多模态": "multimodal",
    "图像": "image",
    "检索": "retrieval",
    ...
}
```

**工作原理**：当遇到中文 token 时，先尝试精确查找（O(1)），再做子串匹配——将中文关键词翻译为对应的英文词，一起加入查询 token 列表：

```
用户输入: "人脸识别训练"
分词:     ["人脸识别训练"]
扩展后:   ["人脸识别训练", "face", "recognition", "training"]
                            ↑ 来自 _ZH_EN_MAP 子串匹配
```

这样中文查询就能匹配到英文知识库中的相关文档。

### BM25 评分算法

BM25（Best Matching 25）是信息检索领域经典的排序算法，本系统采用轻量简化版本：

#### 公式

对于查询 Q 和文档 D，BM25 分数为：

```
Score(Q, D) = Σ  IDF(qi) × f(qi, D) × (k1 + 1)
              qi            ──────────────────────────────
                            f(qi, D) + k1 × (1 - b + b × |D| / avgdl)
```

其中：

| 符号 | 含义 | 本系统取值 |
|------|------|-----------|
| `qi` | 查询中的第 i 个 token | — |
| `f(qi, D)` | token qi 在文档 D 中的词频（Term Frequency） | — |
| `\|D\|` | 文档 D 的 token 总数（文档长度） | — |
| `avgdl` | 所有文档的平均长度 | 动态计算 |
| `k1` | 词频饱和参数，控制 TF 增长速度 | **1.2** |
| `b` | 文档长度归一化参数 | **0.75** |
| `IDF(qi)` | 逆文档频率，衡量 token 的稀有程度 | 见下方 |

#### IDF 计算

```
IDF(qi) = log( (N - df(qi) + 0.5) / (df(qi) + 0.5) + 1 )
```

- `N` = 知识库文档总数
- `df(qi)` = 包含 token qi 的文档数量
- 一个 token 出现在越少的文档中，IDF 越高（越有区分力）

#### 直觉解释

- **TF 部分**：一个词在文档中出现的频率越高，该文档越可能相关。但通过 k1 参数进行饱和处理，避免高频词过度主导。
- **IDF 部分**：在整个知识库中很少出现的词（如 "Partial FC"）比常见词（如 "learning"）更有检索价值。
- **文档长度归一化**：通过参数 b 调整，避免长文档仅因包含更多词而获得不公平的高分。

#### 数值示例

假设用户问 `"Partial FC face recognition"`：

```
查询 tokens: ["partial", "fc", "face", "recognition"]

文档: InsightFace 项目（包含 "partial fc", "face recognition" 等关键词）
  - "partial" 出现 2 次, IDF=3.1  →  贡献 ≈ 3.1 × 2.2/(2+1.2×0.7) = 2.4
  - "fc"      出现 2 次, IDF=2.8  →  贡献 ≈ 2.8 × 2.2/(2+1.2×0.7) = 2.2
  - "face"    出现 5 次, IDF=1.5  →  贡献 ≈ 1.5 × 5.5/(5+1.2×0.7) = 1.5
  - "recognition" 出现 3 次, IDF=1.8 → 贡献 ≈ ...
  总分 ≈ 8.5 ✓ 高于阈值 0.5，命中

文档: LLaVA-OneVision-1.5（不含 "partial", "fc", "face" 等）
  总分 ≈ 0.2 ✗ 低于阈值，不返回
```

最终返回分数最高的 **top_k=3** 个文档。

---

## 上下文注入（Context Injection）

检索到的文档通过 `format_context()` 格式化为结构化的 Markdown 文本，然后追加到 System Prompt 末尾：

```python
# chat.py 中的关键代码
system_content = SYSTEM_PROMPT
if rag_context:
    system_content += (
        "\n\n# Retrieved Context (RAG)\n"
        "以下是根据用户提问从知识库中检索到的相关信息，请结合这些信息回答：\n\n"
        + rag_context
    )
```

格式化后的上下文示例：

```markdown
**Killing Two Birds with One Stone: Efficient and Robust Training of Face Recognition CNNs by Partial FC**
Authors: Xiang An, Jiankang Deng, ...
Venue: CVPR 2022
Paper: https://arxiv.org/abs/2203.15565
Code: https://github.com/deepinsight/insightface/...
Summary: This CVPR 2022 paper introduces Partial FC, ...

---

**InsightFace**
URL: https://github.com/deepinsight/insightface
Stars: 27k+
Role: 2nd largest contributor
Description: State-of-the-art 2D and 3D face analysis toolbox. ...
```

这样 LLM 就能利用这些精确的元数据（论文链接、Star 数、会议名称等）来生成有据可依的回答。

---

## 端到端数据流

以用户提问 **"请介绍一下 Partial FC"** 为例：

```
1. 前端发送:
   POST /api/chat
   {"messages": [{"role": "user", "content": "请介绍一下 Partial FC"}]}

2. chat.py 提取最新用户消息:
   last_user_msg = "请介绍一下 Partial FC"

3. rag_utils.search("请介绍一下 Partial FC", top_k=3):
   a) 分词:     ["partial", "fc"]（中文停用词被过滤）
   b) BM25 打分: 对知识库 26 个文档逐一计算分数
   c) 返回 Top-3:
      - InsightFace 项目         (score: 10.2)
      - Partial FC CVPR 2022     (score: 8.1)
      - Partial FC ICCVW 2021    (score: 7.1)

4. format_context() 将 3 个文档格式化为 Markdown

5. 构建完整的 System Prompt:
   [原始 SYSTEM_PROMPT]
   +
   [# Retrieved Context (RAG)]
   [3 个文档的格式化内容]

6. 调用 DashScope API:
   messages = [
     {"role": "system", "content": "完整 System Prompt + RAG 上下文"},
     {"role": "user", "content": "请介绍一下 Partial FC"}
   ]

7. LLM 利用检索到的具体信息生成回答，包含准确的论文链接和数据
```

---

## 设计取舍与优势

### 为什么选择 BM25 而不是向量检索？

| 特性 | BM25（本系统） | 向量检索（如 FAISS） |
|------|---------------|---------------------|
| 外部依赖 | ✅ 零依赖，纯 Python 标准库 | ❌ 需要 embedding 模型 + 向量库 |
| 冷启动时间 | ✅ < 10ms | ❌ 模型加载耗时 |
| Vercel 兼容 | ✅ 完美适配 serverless | ❌ 内存/包大小限制 |
| 语义理解 | ⚠️ 关键词级别 | ✅ 语义级别 |
| 适合场景 | ✅ 小型知识库（< 100 文档） | ✅ 大型知识库（10k+ 文档） |

**本系统的知识库仅 26 个文档**，BM25 完全够用，且零外部依赖、极快的冷启动完美契合 Vercel serverless 环境。

### 核心优势

1. **零依赖**：不需要向量数据库、Embedding 模型或任何额外服务
2. **极低延迟**：知识库加载后缓存在内存中，检索耗时 < 1ms
3. **跨语言**：中文查询通过翻译字典映射为英文，覆盖常见研究术语
4. **可维护**：添加新论文只需编辑 `knowledge_base.json`，无需重建索引
5. **优雅降级**：如果检索无结果，系统回退到纯 System Prompt 模式，不影响基本功能

---

## 相关文件

| 文件 | 功能 |
|------|------|
| [`api/rag_utils.py`](api/rag_utils.py) | RAG 检索引擎（分词、BM25 打分、格式化） |
| [`api/knowledge_base.json`](api/knowledge_base.json) | 知识库（论文 + GitHub 项目） |
| [`api/chat.py`](api/chat.py) | Chat API，集成 RAG 检索 |
| [`_data/publications.yaml`](_data/publications.yaml) | 论文原始数据（knowledge_base.json 的数据来源） |
