"""
数据库连接工具
提供数据库连接的共享函数
"""

import os
import logging

logger = logging.getLogger(__name__)


def get_db_connection():
    """获取数据库连接
    
    Returns:
        psycopg2 connection object with RealDictCursor, or None if connection fails
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    database_url = os.getenv("POSTGRES_URL")
    if not database_url:
        logger.warning("POSTGRES_URL environment variable not set")
        return None
    
    try:
        # Neon Postgres URL 格式可能需要转换
        # 如果是 postgres:// 开头，改为 postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None
