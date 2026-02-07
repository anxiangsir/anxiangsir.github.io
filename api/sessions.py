"""
会话列表 API
查询所有会话的统计信息
"""

import os
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def get_db_connection():
    """获取数据库连接"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    database_url = os.getenv("POSTGRES_URL")
    if not database_url:
        return None
    
    try:
        # Vercel Postgres URL 格式可能需要转换
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    """查询所有会话列表及统计信息"""
    # 可选的分页参数
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库不可用"}), 503
    
    try:
        cursor = conn.cursor()
        
        # 查询所有会话及其统计信息
        cursor.execute(
            """
            SELECT 
                session_id,
                COUNT(*) as message_count,
                MIN(created_at) as first_message_at,
                MAX(created_at) as last_message_at,
                MAX(user_agent) as user_agent
            FROM chat_logs
            GROUP BY session_id
            ORDER BY MAX(created_at) DESC
            LIMIT %s OFFSET %s
            """,
            (per_page, offset)
        )
        sessions = cursor.fetchall()
        
        # 查询总会话数
        cursor.execute("SELECT COUNT(DISTINCT session_id) as total FROM chat_logs")
        total_result = cursor.fetchone()
        total_sessions = total_result["total"] if total_result else 0
        
        cursor.close()
        conn.close()
        
        # 转换为 JSON 友好格式
        result = []
        for session in sessions:
            result.append({
                "session_id": str(session["session_id"]),
                "message_count": session["message_count"],
                "first_message_at": session["first_message_at"].isoformat(),
                "last_message_at": session["last_message_at"].isoformat(),
                "user_agent": session["user_agent"]
            })
        
        return jsonify({
            "success": True,
            "total": total_sessions,
            "page": page,
            "per_page": per_page,
            "sessions": result
        }), 200
        
    except Exception as e:
        logger.error(f"查询会话列表失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": "查询失败"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
