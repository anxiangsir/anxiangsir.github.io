# Vercel Postgres 数据库配置教程

本教程将指导您如何从零开始为本项目配置 Vercel Postgres 数据库，用于存储对话记录。

## 📋 目录

1. [前置条件](#前置条件)
2. [创建 Vercel Postgres 数据库](#创建-vercel-postgres-数据库)
3. [初始化数据库表](#初始化数据库表)
4. [环境变量配置](#环境变量配置)
5. [本地开发](#本地开发)
6. [部署到 Vercel](#部署到-vercel)
7. [API 使用说明](#api-使用说明)
8. [常见问题 FAQ](#常见问题-faq)

---

## 前置条件

在开始之前，请确保您具备以下条件：

- ✅ **Vercel 账号**：注册免费账号 [https://vercel.com/signup](https://vercel.com/signup)
- ✅ **Node.js**：版本 16.x 或更高（用于本地开发）
- ✅ **Python 3.8+**：用于运行 API 服务
- ✅ **Git**：用于代码管理
- ✅ **Vercel CLI**（可选）：方便本地开发，可通过 `npm install -g vercel` 安装

---

## 创建 Vercel Postgres 数据库

### 步骤 1：登录 Vercel Dashboard

1. 访问 [https://vercel.com](https://vercel.com) 并登录您的账号
2. 进入您的项目 Dashboard

### 步骤 2：创建数据库

1. 在 Vercel Dashboard 顶部导航栏中，点击 **Storage** 标签
   ![Storage Tab](https://vercel.com/_next/image?url=%2Fdocs-proxy%2Fstatic%2Fdocs%2Fstorage%2Foverview.png&w=3840&q=75)

2. 点击 **Create Database** 按钮

3. 选择 **Postgres** 数据库类型
   ![Select Postgres](https://vercel.com/_next/image?url=%2Fdocs-proxy%2Fstatic%2Fdocs%2Fstorage%2Fpostgres%2Fquickstart%2Fcreate-database.png&w=3840&q=75)

4. 配置数据库：
   - **Database Name**：输入数据库名称，例如 `chat-history-db`
   - **Region**：选择离您用户最近的区域（推荐选择 `Hong Kong (hkg1)` 或 `Singapore (sin1)` 以获得更低延迟）
   - **Pricing Plan**：选择 `Hobby`（免费套餐，适合个人项目）

5. 点击 **Create** 按钮创建数据库

### 步骤 3：关联数据库到项目

1. 创建完成后，您会看到数据库详情页
2. 点击 **Connect Project** 按钮
3. 选择您的项目（`anxiangsir.github.io`）
4. 点击 **Connect** 完成关联

> **提示**：关联后，Vercel 会自动将数据库连接信息作为环境变量注入到您的项目中。

---

## 初始化数据库表

创建数据库后，需要执行 SQL 脚本来创建表结构。

### 方法 1：使用 Vercel Dashboard（推荐）

1. 在 Vercel Dashboard 中，进入 **Storage** → 选择您刚创建的数据库
2. 点击 **Data** 标签
3. 点击 **Query** 按钮打开 SQL 编辑器
4. 复制 `schema.sql` 文件的全部内容并粘贴到编辑器中：

```sql
-- Vercel Postgres 数据库 Schema
-- 用于存储对话记录

-- 创建对话记录表
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为 session_id 创建索引，提高查询效率
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);

-- 为 created_at 创建索引，支持按时间排序查询
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

-- 为 session_id 和 created_at 组合创建复合索引，优化会话历史查询
CREATE INDEX IF NOT EXISTS idx_conversations_session_created ON conversations(session_id, created_at);
```

5. 点击 **Run** 执行 SQL 脚本
6. 确认看到 "Query executed successfully" 消息

### 方法 2：使用 Vercel CLI（本地执行）

如果您安装了 Vercel CLI，可以通过命令行执行：

```bash
# 1. 拉取环境变量到本地
vercel env pull .env.local

# 2. 安装 psql 工具（如果尚未安装）
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql-client

# 3. 从 .env.local 获取 POSTGRES_URL 并执行 schema.sql
psql $(grep POSTGRES_URL .env.local | cut -d '=' -f2) < schema.sql
```

---

## 环境变量配置

### Vercel 自动注入的环境变量

当您将数据库关联到项目后，Vercel 会自动注入以下环境变量（**无需手动配置**）：

| 环境变量 | 说明 |
|---------|------|
| `POSTGRES_URL` | 完整的数据库连接字符串（包含 SSL） |
| `POSTGRES_URL_NON_POOLING` | 非连接池的连接字符串 |
| `POSTGRES_USER` | 数据库用户名 |
| `POSTGRES_HOST` | 数据库主机地址 |
| `POSTGRES_PASSWORD` | 数据库密码 |
| `POSTGRES_DATABASE` | 数据库名称 |

### 需要手动配置的环境变量

除了数据库连接，您还需要配置以下环境变量：

1. 在 Vercel Dashboard 中，进入您的项目
2. 点击 **Settings** → **Environment Variables**
3. 添加以下环境变量：

| 变量名 | 值 | 说明 |
|-------|---|------|
| `DASHSCOPE_API_KEY` | `sk-xxxxx` | 您的阿里云百炼 API Key（从 [控制台](https://help.aliyun.com/model-studio/getting-started/models) 获取） |

4. 点击 **Save** 保存

> **注意**：环境变量分为三种类型：
> - **Production**：生产环境（主分支部署）
> - **Preview**：预览环境（PR 和分支部署）
> - **Development**：本地开发（通过 `vercel env pull` 拉取）
> 
> 建议为所有三种环境都配置相同的值。

---

## 本地开发

### 步骤 1：克隆项目

```bash
git clone https://github.com/anxiangsir/anxiangsir.github.io.git
cd anxiangsir.github.io
```

### 步骤 2：拉取环境变量

使用 Vercel CLI 将云端的环境变量拉取到本地：

```bash
# 安装 Vercel CLI（如果尚未安装）
npm install -g vercel

# 登录 Vercel
vercel login

# 关联本地项目到 Vercel 项目
vercel link

# 拉取环境变量到 .env.local
vercel env pull .env.local
```

执行后，您会在项目根目录看到 `.env.local` 文件，其中包含所有环境变量。

### 步骤 3：安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 4：启动本地 API 服务

```bash
# 启动聊天 API（端口 5000）
python api/chat.py

# 或启动对话历史 API（端口 5001）
python api/chat_history.py

# 或启动会话列表 API（端口 5002）
python api/sessions.py
```

### 步骤 5：启动前端服务

在另一个终端窗口中：

```bash
# 使用 Python 内置 HTTP 服务器
python -m http.server 8000

# 或使用 Node.js live-server
npm install -g live-server
live-server
```

### 步骤 6：访问本地站点

打开浏览器访问 [http://localhost:8000](http://localhost:8000)

---

## 部署到 Vercel

### 自动部署（推荐）

Vercel 已经与您的 GitHub 仓库关联，每次推送代码到 `main` 分支时会自动触发部署：

```bash
git add .
git commit -m "集成 Vercel Postgres 数据库"
git push origin main
```

### 手动部署

如果需要手动部署，可以使用 Vercel CLI：

```bash
vercel --prod
```

### 验证部署

1. 部署完成后，访问您的 Vercel 生产 URL
2. 打开浏览器开发者工具（F12）→ Network 标签
3. 在聊天界面发送一条消息
4. 检查 `/api/chat` 请求是否成功返回（状态码 200）

---

## API 使用说明

### 1. POST /api/chat — 发送聊天消息（集成数据库保存）

**功能**：发送消息到聊天 AI，并可选地保存对话记录到数据库。

#### 请求示例

```bash
curl -X POST https://your-vercel-url.vercel.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "550e8400-e29b-41d4-a716-446655440000",
    "messages": [
      {"role": "user", "content": "介绍一下安翔的研究方向"}
    ]
  }'
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `sessionId` | String (UUID) | 否 | 会话 ID，如果提供则自动保存对话记录到数据库 |
| `messages` | Array | 是 | 对话历史数组，每个元素包含 `role` 和 `content` |
| `message` | String | 否 | 单条消息（向后兼容，如果提供了 `messages` 则忽略） |

#### 响应示例

```json
{
  "reply": "安翔 (Xiang An) 是一位在计算机视觉和多模态大模型领域深耕的研究科学家..."
}
```

---

### 2. POST /api/chat_history — 保存对话记录

**功能**：手动保存一条对话记录到数据库。

#### 请求示例

```bash
curl -X POST https://your-vercel-url.vercel.app/api/chat_history \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "550e8400-e29b-41d4-a716-446655440000",
    "role": "user",
    "content": "介绍一下安翔的研究方向"
  }'
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `sessionId` | String (UUID) | 是 | 会话 ID |
| `role` | String | 是 | 角色，必须是 `user` 或 `assistant` |
| `content` | String | 是 | 对话内容 |

#### 响应示例

```json
{
  "success": true,
  "id": 123,
  "created_at": "2026-02-07T00:00:00.000Z"
}
```

---

### 3. GET /api/chat_history?sessionId=xxx — 获取对话历史

**功能**：获取某个会话的所有对话记录（按时间正序）。

#### 请求示例

```bash
curl "https://your-vercel-url.vercel.app/api/chat_history?sessionId=550e8400-e29b-41d4-a716-446655440000"
```

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `sessionId` | String (UUID) | 是 | 会话 ID |

#### 响应示例

```json
{
  "success": true,
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "id": 1,
      "sessionId": "550e8400-e29b-41d4-a716-446655440000",
      "role": "user",
      "content": "介绍一下安翔的研究方向",
      "createdAt": "2026-02-07T00:00:00.000Z"
    },
    {
      "id": 2,
      "sessionId": "550e8400-e29b-41d4-a716-446655440000",
      "role": "assistant",
      "content": "安翔 (Xiang An) 是一位在计算机视觉和多模态大模型领域深耕的研究科学家...",
      "createdAt": "2026-02-07T00:00:01.000Z"
    }
  ],
  "count": 2
}
```

---

### 4. GET /api/sessions — 获取所有会话列表

**功能**：获取所有会话的元数据（会话 ID、消息数量、时间戳）。

#### 请求示例

```bash
curl "https://your-vercel-url.vercel.app/api/sessions"
```

#### 响应示例

```json
{
  "success": true,
  "sessions": [
    {
      "sessionId": "550e8400-e29b-41d4-a716-446655440000",
      "messageCount": 10,
      "firstMessageAt": "2026-02-06T10:00:00.000Z",
      "lastMessageAt": "2026-02-07T00:00:00.000Z"
    },
    {
      "sessionId": "660f9511-f39c-52e5-b827-557766551111",
      "messageCount": 5,
      "firstMessageAt": "2026-02-05T15:30:00.000Z",
      "lastMessageAt": "2026-02-05T16:00:00.000Z"
    }
  ],
  "count": 2
}
```

---

## 常见问题 FAQ

### Q1: 如何查看数据库中的数据？

**A1**: 有两种方法：

1. **使用 Vercel Dashboard**：
   - 进入 Storage → 选择数据库 → Data 标签
   - 在 Query 编辑器中执行 `SELECT * FROM conversations ORDER BY created_at DESC LIMIT 10;`

2. **使用本地 psql 客户端**：
   ```bash
   # 从 .env.local 获取连接字符串
   psql $(grep POSTGRES_URL .env.local | cut -d '=' -f2)
   
   # 执行查询
   SELECT * FROM conversations ORDER BY created_at DESC LIMIT 10;
   ```

---

### Q2: 为什么本地开发时提示 "数据库连接失败"？

**A2**: 请检查以下几点：

1. 确认已执行 `vercel env pull .env.local` 拉取环境变量
2. 检查 `.env.local` 文件是否存在且包含 `POSTGRES_URL`
3. 确认您的 IP 没有被 Vercel Postgres 防火墙阻止（默认允许所有 IP）
4. 尝试手动测试连接：
   ```bash
   psql $(grep POSTGRES_URL .env.local | cut -d '=' -f2) -c "SELECT 1;"
   ```

---

### Q3: 数据库连接是否计入 Vercel Hobby 套餐限制？

**A3**: 是的，Vercel Postgres Hobby 套餐有以下限制：

- **存储空间**：256 MB
- **每月计算时间**：60 小时
- **并发连接数**：最多 20 个

对于个人项目和小流量应用，这些限制通常足够使用。如果需要更多资源，可以升级到 Pro 套餐。

---

### Q4: 如何生成 UUID 作为 sessionId？

**A4**: 在前端 JavaScript 中：

```javascript
// 方法 1: 使用 crypto API（推荐）
const sessionId = crypto.randomUUID();

// 方法 2: 使用第三方库 uuid
// npm install uuid
import { v4 as uuidv4 } from 'uuid';
const sessionId = uuidv4();
```

在 Python 中：

```python
import uuid
session_id = str(uuid.uuid4())
```

---

### Q5: 如何清空数据库？

**A5**: 在 Vercel Dashboard 的 Query 编辑器中执行：

```sql
TRUNCATE TABLE conversations;
```

或者删除并重新创建表：

```sql
DROP TABLE conversations;
-- 然后重新执行 schema.sql 中的 CREATE TABLE 语句
```

---

### Q6: 如何备份数据库？

**A6**: 使用 `pg_dump` 工具：

```bash
# 导出数据到 SQL 文件
pg_dump $(grep POSTGRES_URL .env.local | cut -d '=' -f2) > backup.sql

# 恢复数据
psql $(grep POSTGRES_URL .env.local | cut -d '=' -f2) < backup.sql
```

---

### Q7: 部署后 API 返回 500 错误怎么办？

**A7**: 请检查以下几点：

1. **查看日志**：在 Vercel Dashboard → Deployments → 选择最新部署 → Functions 标签，查看函数日志
2. **检查环境变量**：确认 `POSTGRES_URL` 和 `DASHSCOPE_API_KEY` 都已正确配置
3. **验证数据库表**：确认 `conversations` 表已创建
4. **检查代码错误**：查看日志中的 Python 异常堆栈

---

### Q8: 如何为数据库添加认证/授权？

**A8**: 本项目的 API 目前没有内置认证机制。如果需要保护 API，可以：

1. **使用 Vercel 的 Edge Config**：存储 API Token 并在请求中验证
2. **集成第三方身份验证**：如 Auth0、Clerk、NextAuth.js
3. **添加简单的 Bearer Token**：
   ```python
   @app.route("/api/chat_history", methods=["POST"])
   def save_chat_history():
       auth_header = request.headers.get("Authorization")
       if auth_header != "Bearer YOUR_SECRET_TOKEN":
           return jsonify({"error": "未授权"}), 401
       # ... 后续逻辑
   ```

---

### Q9: 支持哪些数据库客户端工具？

**A9**: Vercel Postgres 基于 PostgreSQL，支持所有标准的 PostgreSQL 客户端：

- **命令行工具**：`psql`
- **GUI 工具**：
  - [DBeaver](https://dbeaver.io/)
  - [pgAdmin](https://www.pgadmin.org/)
  - [TablePlus](https://tableplus.com/)
  - [Postico](https://eggerapps.at/postico/)（macOS）

连接时使用 `POSTGRES_URL` 作为连接字符串即可。

---

### Q10: 如何迁移到其他数据库（如 Supabase、PlanetScale）？

**A10**: 本项目使用标准的 `psycopg2` Python 库，可以轻松切换到任何 PostgreSQL 兼容的数据库：

1. 获取新数据库的连接字符串
2. 在 Vercel 环境变量中将 `POSTGRES_URL` 修改为新的连接字符串
3. 执行 `schema.sql` 初始化新数据库
4. 重新部署项目

---

## 🎉 完成！

恭喜您成功配置了 Vercel Postgres 数据库！现在您的聊天应用可以持久化存储对话记录了。

如果遇到任何问题，请参考上述 FAQ 或查看：
- [Vercel Postgres 官方文档](https://vercel.com/docs/storage/vercel-postgres)
- [项目 GitHub Issues](https://github.com/anxiangsir/anxiangsir.github.io/issues)

---

**文档版本**: v1.0.0  
**最后更新**: 2026-02-07
