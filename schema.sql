-- Neon Postgres 数据库 Schema
-- 用于存储聊天机器人对话记录

-- 创建对话日志表
CREATE TABLE IF NOT EXISTS chat_logs (
  id SERIAL PRIMARY KEY,
  session_id UUID NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_logs(created_at);

-- 注释说明
COMMENT ON TABLE chat_logs IS '聊天对话记录表';
COMMENT ON COLUMN chat_logs.session_id IS '会话标识符（UUID），标识一次完整的对话会话';
COMMENT ON COLUMN chat_logs.role IS '消息角色：user（用户）或 assistant（助手）';
COMMENT ON COLUMN chat_logs.content IS '消息内容';
COMMENT ON COLUMN chat_logs.user_agent IS '用户浏览器信息（可选）';
COMMENT ON COLUMN chat_logs.created_at IS '消息创建时间';

-- Google Scholar 引用数缓存表
CREATE TABLE IF NOT EXISTS scholar_cache (
  key VARCHAR(64) PRIMARY KEY,
  value INTEGER NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE scholar_cache IS 'Google Scholar 数据缓存表';
COMMENT ON COLUMN scholar_cache.key IS '缓存键（如 citations）';
COMMENT ON COLUMN scholar_cache.value IS '缓存值（如引用次数）';
COMMENT ON COLUMN scholar_cache.updated_at IS '最后更新时间';
