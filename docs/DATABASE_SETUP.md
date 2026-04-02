# Neon Postgres 数据库集成教程

本文档详细介绍如何集成 [Neon](https://neon.tech/) Postgres 数据库，用于自动保存用户与聊天机器人的对话记录。

> **推荐方案**：直接在 Neon 控制台创建数据库，然后将连接 URL 配置到 Vercel 环境变量中。也可以通过 Vercel Storage 集成（底层同样使用 Neon）。

## 目录

1. [功能概述](#功能概述)
2. [方案一：直接使用 Neon（推荐）](#方案一直接使用-neon推荐)
3. [方案二：通过 Vercel Storage 集成](#方案二通过-vercel-storage-集成)
4. [初始化数据库表结构](#初始化数据库表结构)
5. [环境变量说明](#环境变量说明)
6. [本地开发配置](#本地开发配置)
7. [API 接口说明](#api-接口说明)
8. [查看存储的对话记录](#查看存储的对话记录)
9. [故障排查](#故障排查)

---

## 功能概述

本项目使用 Neon Postgres 数据库，实现以下功能：

- ✅ **自动保存对话**：用户与聊天机器人的每轮对话自动保存到远程数据库
- ✅ **会话追踪**：通过 UUID 标识每个会话，支持对话历史查询
- ✅ **静默操作**：数据库保存在后台静默进行，不影响用户聊天体验
- ✅ **错误容错**：数据库保存失败不会影响正常聊天功能
- ✅ **管理接口**：提供 API 查询会话列表和对话历史

---

## 方案一：直接使用 Neon（推荐）

### 步骤 1：注册并创建数据库

1. 访问 [Neon Console](https://console.neon.tech/) 并注册/登录
2. 点击 **New Project** 创建新项目
3. **Project Name**：输入项目名称，例如 `chat-logs`
4. **Region**：选择离您用户最近的地区（建议选择 `Asia Pacific (Singapore)`）
5. 点击 **Create Project**

### 步骤 2：获取连接 URL

1. 项目创建后，在 **Dashboard** 页面找到 **Connection string**
2. 复制完整的连接 URL，格式类似：
   ```
   postgresql://username:password@ep-xxx.region.neon.tech/dbname?sslmode=require
   ```

### 步骤 3：配置 Vercel 环境变量

1. 进入 Vercel 项目设置：**Project Settings** → **Environment Variables**
2. 添加环境变量：
   - **Key**: `POSTGRES_URL`
   - **Value**: 粘贴从 Neon 复制的连接 URL
   - **Environments**: 选择 `Production`, `Preview`, `Development`
3. 点击 **Save** 保存
4. **重新部署** 项目使环境变量生效

---

## 方案二：通过 Vercel Storage 集成

### 步骤 1：登录 Vercel 控制台

访问 [Vercel Dashboard](https://vercel.com/dashboard) 并登录您的账户。

### 步骤 2：进入存储（Storage）页面

1. 在左侧导航栏中，点击 **Storage**
2. 点击 **Create Database** 按钮
3. 选择 **Postgres** 数据库类型

### 步骤 3：配置数据库

1. **Database Name**：输入数据库名称，例如 `chat-logs-db`
2. **Region**：选择离您用户最近的地区（建议选择 `Hong Kong (hkg1)` 或 `Singapore (sin1)`）
3. 点击 **Create** 按钮

创建完成后，Vercel 会自动生成一个 Neon Postgres 数据库实例。

---

### 关联数据库到项目

### 自动关联（推荐）

1. 在数据库详情页面，点击 **Connect Project** 按钮
2. 选择您的项目（例如 `anxiangsir-github-io`）
3. 选择要关联的环境：
   - ✅ **Production** （生产环境，必选）
   - ✅ **Preview** （预览环境，可选）
   - ✅ **Development** （开发环境，可选）
4. 点击 **Connect** 按钮

关联完成后，Vercel 会自动将以下环境变量注入到您的项目中：

- `POSTGRES_URL` - 完整的数据库连接 URL
- `POSTGRES_PRISMA_URL` - Prisma 专用连接 URL
- `POSTGRES_URL_NON_POOLING` - 非连接池 URL
- `POSTGRES_USER` - 数据库用户名
- `POSTGRES_HOST` - 数据库主机地址
- `POSTGRES_PASSWORD` - 数据库密码
- `POSTGRES_DATABASE` - 数据库名称

### 手动关联（备用方案）

如果自动关联失败，可以手动配置：

1. 进入项目设置：**Project Settings** → **Environment Variables**
2. 从数据库详情页面复制 `POSTGRES_URL`
3. 添加环境变量：
   - **Key**: `POSTGRES_URL`
   - **Value**: 粘贴复制的连接 URL
   - **Environments**: 选择 `Production`, `Preview`, `Development`
4. 点击 **Save** 保存

---

## 初始化数据库表结构

### 方法 1：使用 Vercel Postgres 查询界面（推荐）

1. 在 Vercel Dashboard 中，进入 **Storage** → 选择您的数据库
2. 点击 **Query** 标签页
3. 打开项目根目录的 `schema.sql` 文件，复制全部内容
4. 粘贴到查询编辑器中
5. 点击 **Run Query** 按钮执行

执行成功后，您会看到确认消息，表结构已创建完成。

### 方法 2：使用 psql 命令行工具

如果您已安装 PostgreSQL 客户端，可以通过命令行执行：

```bash
# 从 Vercel Dashboard 复制 POSTGRES_URL
export POSTGRES_URL="postgres://..."

# 执行 schema.sql
psql $POSTGRES_URL < schema.sql
```

### 表结构说明

`chat_logs` 表包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | SERIAL | 主键，自增 ID |
| `session_id` | UUID | 会话标识符，用于追踪一次完整对话 |
| `role` | VARCHAR(20) | 消息角色：`user`（用户）或 `assistant`（助手） |
| `content` | TEXT | 消息内容 |
| `user_agent` | TEXT | 用户浏览器信息（可选） |
| `created_at` | TIMESTAMP | 消息创建时间 |

索引：
- `idx_chat_session`：基于 `session_id` 的索引，优化会话查询
- `idx_chat_created`：基于 `created_at` 的索引，优化时间范围查询

---

## 环境变量说明

### 自动注入的环境变量

通过 Vercel Storage 集成时，Vercel 会自动注入以下环境变量。直接使用 Neon 时，只需手动配置 `POSTGRES_URL` 即可：

```bash
# 主要连接 URL（推荐使用）
POSTGRES_URL="postgres://username:password@host/database?sslmode=require"

# 其他可用变量
POSTGRES_PRISMA_URL="postgres://username:password@host/database?pgbouncer=true&sslmode=require"
POSTGRES_URL_NON_POOLING="postgres://username:password@host/database?sslmode=require"
POSTGRES_USER="username"
POSTGRES_HOST="host.region.neon.tech"
POSTGRES_PASSWORD="password"
POSTGRES_DATABASE="database"
```

### 在代码中使用

Python 代码中通过 `os.getenv()` 读取环境变量：

```python
import os
database_url = os.getenv("POSTGRES_URL")
```

JavaScript 代码中（仅限服务端）：

```javascript
const databaseUrl = process.env.POSTGRES_URL;
```

⚠️ **重要**：
- 环境变量仅在 **服务端** 可用（API 路由、Serverless Functions）
- 前端 JavaScript 无法访问这些环境变量（出于安全考虑）
- 数据库连接 URL 包含敏感信息，切勿在前端代码或 Git 中暴露

---

## 本地开发配置

### 步骤 1：安装 Vercel CLI

```bash
npm install -g vercel
```

### 步骤 2：登录 Vercel

```bash
vercel login
```

### 步骤 3：拉取环境变量

在项目根目录执行：

```bash
vercel env pull .env.local
```

这会创建一个 `.env.local` 文件，包含所有生产环境的环境变量（包括 `POSTGRES_URL`）。

### 步骤 4：运行本地开发服务器

```bash
# 安装依赖
pip install -r requirements.txt

# 运行本地服务器（Vercel 会自动加载 .env.local）
vercel dev
```

或者使用 Flask 直接运行：

```bash
# 手动加载环境变量
export $(cat .env.local | xargs)

# 运行 Flask 开发服务器
cd api
python chat.py
```

### ⚠️ 安全提示

- `.env.local` 文件已在 `.gitignore` 中，**不要**将其提交到 Git
- 不要在公开场合分享 `.env.local` 中的内容

---

## API 接口说明

项目提供了 3 个 API 端点用于对话记录管理：

### 1. POST /api/chat-log - 保存对话记录

**用途**：保存一条用户或助手的消息到数据库。

**请求示例**：

```bash
curl -X POST https://anxiangsir-github-io.vercel.app/api/chat-log \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "user",
    "content": "你好，安翔",
    "user_agent": "Mozilla/5.0..."
  }'
```

**请求参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `session_id` | UUID | 是 | 会话标识符 |
| `role` | String | 是 | `user` 或 `assistant` |
| `content` | String | 是 | 消息内容 |
| `user_agent` | String | 否 | 浏览器信息，如果未提供则使用请求头中的 User-Agent |

**响应示例（成功）**：

```json
{
  "success": true,
  "id": 123,
  "created_at": "2025-01-28T10:30:00.000Z"
}
```

**响应示例（数据库不可用，静默失败）**：

```json
{
  "success": true,
  "message": "日志保存已跳过"
}
```

### 2. GET /api/chat-log?sessionId=xxx - 查询会话对话记录

**用途**：查询某个会话的完整对话历史。

**请求示例**：

```bash
curl "https://anxiangsir-github-io.vercel.app/api/chat-log?sessionId=550e8400-e29b-41d4-a716-446655440000"
```

**请求参数**：

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `sessionId` | UUID | 是 | 要查询的会话 ID |

**响应示例**：

```json
{
  "success": true,
  "count": 4,
  "logs": [
    {
      "id": 1,
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "user",
      "content": "你好，安翔",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2025-01-28T10:30:00.000Z"
    },
    {
      "id": 2,
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "assistant",
      "content": "你好！我是安翔的 AI 助手...",
      "user_agent": null,
      "created_at": "2025-01-28T10:30:05.000Z"
    }
  ]
}
```

### 3. GET /api/sessions - 查询所有会话列表

**用途**：查询所有会话的统计信息（管理用）。

**请求示例**：

```bash
curl "https://anxiangsir-github-io.vercel.app/api/sessions?page=1&per_page=20"
```

**请求参数**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | Integer | 否 | 1 | 页码 |
| `per_page` | Integer | 否 | 50 | 每页数量 |

**响应示例**：

```json
{
  "success": true,
  "total": 150,
  "page": 1,
  "per_page": 20,
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "message_count": 12,
      "first_message_at": "2025-01-28T10:30:00.000Z",
      "last_message_at": "2025-01-28T10:45:00.000Z",
      "user_agent": "Mozilla/5.0..."
    }
  ]
}
```

---

## 查看存储的对话记录

### 方法 1：使用 Vercel Postgres 查询界面

1. 进入 **Vercel Dashboard** → **Storage** → 选择您的数据库
2. 点击 **Query** 标签页
3. 执行 SQL 查询：

```sql
-- 查看最近 10 条对话记录
SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT 10;

-- 查看某个会话的所有记录
SELECT * FROM chat_logs 
WHERE session_id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY created_at ASC;

-- 统计总会话数
SELECT COUNT(DISTINCT session_id) as total_sessions FROM chat_logs;

-- 统计总消息数
SELECT COUNT(*) as total_messages FROM chat_logs;

-- 查看最活跃的会话
SELECT 
  session_id, 
  COUNT(*) as message_count,
  MIN(created_at) as first_message,
  MAX(created_at) as last_message
FROM chat_logs
GROUP BY session_id
ORDER BY message_count DESC
LIMIT 10;
```

### 方法 2：使用 API 接口

在浏览器或 Postman 中访问：

```
# 查看所有会话
https://anxiangsir-github-io.vercel.app/api/sessions

# 查看特定会话的对话记录（替换为实际的 session_id）
https://anxiangsir-github-io.vercel.app/api/chat-log?sessionId=YOUR_SESSION_ID
```

### 方法 3：使用 psql 命令行

```bash
# 设置连接 URL
export POSTGRES_URL="postgres://..."

# 连接到数据库
psql $POSTGRES_URL

# 执行查询
SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT 10;
```

---

## 故障排查

### 问题 1：API 返回 "数据库不可用"

**可能原因**：
- 数据库未正确关联到项目
- 环境变量 `POSTGRES_URL` 未设置

**解决方法**：
1. 在 Vercel Dashboard 中检查 **Storage** → **Connections**，确保数据库已关联
2. 在 **Project Settings** → **Environment Variables** 中检查 `POSTGRES_URL` 是否存在
3. 如果是新添加的环境变量，需要 **重新部署** 项目才能生效

### 问题 2：表不存在错误

**错误信息**：`relation "chat_logs" does not exist`

**解决方法**：
1. 确认是否执行了 `schema.sql` 初始化表结构
2. 在 Vercel Dashboard 的 Query 界面执行：
   ```sql
   SELECT * FROM chat_logs LIMIT 1;
   ```
3. 如果提示表不存在，重新执行 `schema.sql` 的全部内容

### 问题 3：本地开发无法连接数据库

**解决方法**：
1. 确认已执行 `vercel env pull .env.local`
2. 检查 `.env.local` 文件是否存在并包含 `POSTGRES_URL`
3. 使用 `vercel dev` 而非直接运行 Python 文件（`vercel dev` 会自动加载环境变量）

### 问题 4：前端无法保存对话

**检查方法**：
1. 打开浏览器开发者工具（F12）→ **Console** 标签
2. 查看是否有网络请求失败或错误信息
3. 查看 **Network** 标签，确认 POST 请求到 `/api/chat-log` 是否发送
4. 检查响应状态码：
   - `201` - 成功保存
   - `200` + `"message": "日志保存已跳过"` - 数据库不可用，但不影响聊天
   - `400` - 请求参数错误
   - `500` - 服务器错误

**注意**：由于采用了 **静默失败** 策略，即使数据库保存失败，聊天功能仍然正常工作。

### 问题 5：部署后仍无法保存

**解决方法**：
1. 确认数据库已关联到 **Production** 环境
2. 检查是否需要重新部署：**Vercel Dashboard** → **Deployments** → **Redeploy**
3. 查看部署日志，确认没有 Python 包安装失败（特别是 `psycopg2-binary`）

---

## 技术架构说明

### 前端（index.html）

- 使用 `crypto.randomUUID()` 生成会话 ID
- 会话 ID 存储在 `localStorage` 中，浏览器会话期间保持不变
- 每次用户发送消息和收到回复时，异步调用 `/api/chat-log` 保存
- 使用 `fetch()` 静默发送，错误不影响聊天体验

### 后端（API Routes）

- `api/chat_log.py`：处理对话记录的保存和查询
- `api/sessions.py`：处理会话列表查询
- 使用 `psycopg2-binary` 连接 Neon Postgres
- 静默失败：数据库不可用时返回成功响应，记录日志但不抛出错误

### 数据库（Neon Postgres）

- 托管在 [Neon](https://neon.tech/) 平台
- 可直接在 Neon 控制台管理，也可通过 Vercel Storage 集成
- 自动备份和高可用
- 支持连接池（通过 `POSTGRES_PRISMA_URL`）

---

## 最佳实践

1. **环境变量管理**
   - 生产环境：使用 Vercel 自动注入的环境变量
   - 开发环境：使用 `vercel env pull` 同步环境变量
   - 永远不要在代码中硬编码数据库连接信息

2. **错误处理**
   - 前端：静默失败，不影响用户体验
   - 后端：记录日志，返回友好的错误信息

3. **性能优化**
   - 使用数据库索引加速查询
   - 前端异步保存，不阻塞聊天流程
   - 使用连接池减少数据库连接开销

4. **安全考虑**
   - 数据库连接 URL 仅在服务端可用
   - 使用参数化查询防止 SQL 注入
   - 定期审查存储的对话内容，删除敏感信息

5. **监控与维护**
   - 定期检查 Vercel Dashboard 的数据库使用情况
   - 监控 API 错误率和响应时间
   - 根据实际使用情况调整数据库存储容量

---

## 相关链接

- [Neon 文档](https://neon.tech/docs)
- [Vercel Postgres 官方文档](https://vercel.com/docs/storage/vercel-postgres)
- [psycopg2 文档](https://www.psycopg.org/docs/)
- [Vercel CLI 文档](https://vercel.com/docs/cli)

---

## 支持与反馈

如有问题或建议，请联系：
- Email: anxiangsir@outlook.com
- GitHub: https://github.com/anxiangsir
