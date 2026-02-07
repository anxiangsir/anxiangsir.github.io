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

-- 添加表注释
COMMENT ON TABLE conversations IS '对话记录表，存储用户和助手的对话内容';
COMMENT ON COLUMN conversations.id IS '自增主键';
COMMENT ON COLUMN conversations.session_id IS '会话ID（UUID），用于关联同一会话的多条消息';
COMMENT ON COLUMN conversations.role IS '角色：user（用户）或 assistant（助手）';
COMMENT ON COLUMN conversations.content IS '对话内容';
COMMENT ON COLUMN conversations.created_at IS '创建时间，自动生成';
