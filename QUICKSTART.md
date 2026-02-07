# 快速开始指南 (Quick Start)

本指南帮助您快速启用对话历史功能。

## 🚀 5分钟快速部署

### 第 1 步：在 Vercel 创建数据库

1. 登录 [Vercel Dashboard](https://vercel.com)
2. 点击 **Storage** → **Create Database** → 选择 **Postgres**
3. 命名数据库（如 `chat-history-db`），选择区域（推荐 Hong Kong 或 Singapore）
4. 点击 **Connect Project** 关联到您的项目

### 第 2 步：初始化数据库表

1. 在 Vercel Dashboard 中，进入 Storage → 选择数据库 → **Data** 标签
2. 点击 **Query**，粘贴以下 SQL 并执行：

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_session_created ON conversations(session_id, created_at);
```

### 第 3 步：部署

```bash
git push origin main
```

就这么简单！Vercel 会自动：
- 检测到数据库关联
- 注入 `POSTGRES_URL` 环境变量
- 部署所有 API 端点

### 第 4 步：测试

1. 访问您的网站
2. 在聊天框中发送消息
3. 点击页面顶部的 "💾 Chat History" 查看对话记录

---

## 📖 完整文档

详细配置说明请参考 [DATABASE_SETUP.md](DATABASE_SETUP.md)

---

## 🔧 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 拉取环境变量
vercel env pull .env.local

# 启动 API 服务
python api/chat.py         # 端口 5000
python api/chat_history.py # 端口 5001
python api/sessions.py     # 端口 5002

# 启动前端（在另一个终端）
python -m http.server 8000
```

访问 http://localhost:8000

---

## ✨ 功能特性

- ✅ 自动保存每次对话到数据库
- ✅ 会话 ID 自动生成并保存到浏览器
- ✅ 美观的对话历史查看界面
- ✅ 支持查看所有历史会话
- ✅ 按时间正序展示对话
- ✅ 响应式设计，支持移动端

---

## 🆘 遇到问题？

1. **数据库连接失败**：检查 `POSTGRES_URL` 环境变量是否已设置
2. **API 返回 500**：查看 Vercel Dashboard → Deployments → Functions 日志
3. **没有保存对话**：确认数据库表已创建（执行步骤 2）

更多问题请查看 [DATABASE_SETUP.md#常见问题-faq](DATABASE_SETUP.md#常见问题-faq)

---

**提示**：数据库功能是可选的！如果不配置数据库，聊天功能仍然正常工作，只是不会持久化保存对话记录。
