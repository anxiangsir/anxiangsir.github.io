"""
Sessions API service for retrieving all conversation sessions.
Uses Vercel Postgres database to list session metadata.
"""

import logging
import os

from flask import Flask, request, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 从环境变量获取数据库连接信息
POSTGRES_URL = os.getenv("POSTGRES_URL", "")


def get_db_connection():
    """创建并返回数据库连接"""
    if not POSTGRES_URL:
        logger.error("POSTGRES_URL 环境变量未设置")
        return None
    
    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        return conn
    except Exception as e:
        logger.exception("数据库连接失败")
        return None


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """
    获取所有会话列表
    返回每个会话的 session_id、消息数量、最后更新时间
    """
    # 连接数据库
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cursor = conn.cursor()
        
        # 查询所有会话的统计信息
        cursor.execute(
            """
            SELECT 
                session_id,
                COUNT(*) as message_count,
                MIN(created_at) as first_message_at,
                MAX(created_at) as last_message_at
            FROM conversations
            GROUP BY session_id
            ORDER BY last_message_at DESC
            """
        )
        
        rows = cursor.fetchall()
        
        # 转换为 JSON 格式
        sessions = []
        for row in rows:
            sessions.append({
                "sessionId": str(row[0]),
                "messageCount": row[1],
                "firstMessageAt": row[2].isoformat(),
                "lastMessageAt": row[3].isoformat()
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }), 200
        
    except Exception as e:
        logger.exception("获取会话列表失败")
        if conn:
            conn.close()
        return jsonify({"error": "获取失败"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    app.run(host="0.0.0.0", port=port)
