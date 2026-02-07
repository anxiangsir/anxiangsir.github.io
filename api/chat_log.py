"""
聊天对话日志 API
保存和查询用户与聊天机器人的对话记录
"""

import os
import logging
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/api/chat-log", methods=["POST"])
def save_chat_log():
    """保存一条对话记录到数据库"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "无效的请求数据"}), 400
    
    # 验证必需字段
    session_id = data.get("session_id")
    role = data.get("role")
    content = data.get("content")
    
    if not session_id or not role or not content:
        return jsonify({"error": "缺少必需字段：session_id, role, content"}), 400
    
    if role not in ("user", "assistant"):
        return jsonify({"error": "role 必须是 'user' 或 'assistant'"}), 400
    
    # 可选字段
    user_agent = data.get("user_agent") or request.headers.get("User-Agent")
    
    # 连接数据库
    conn = get_db_connection()
    if not conn:
        # 静默失败，不影响聊天体验
        logger.warning("数据库不可用，跳过日志保存")
        return jsonify({"success": True, "message": "日志保存已跳过"}), 200
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_logs (session_id, role, content, user_agent, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id, created_at
            """,
            (session_id, role, content, user_agent)
        )
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "id": result["id"],
            "created_at": result["created_at"].isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"保存对话日志失败: {e}")
        if conn:
            conn.close()
        # 静默失败
        return jsonify({"success": True, "message": "日志保存失败，但不影响聊天"}), 200


@app.route("/api/chat-log", methods=["GET"])
def get_chat_logs():
    """查询某个会话的对话记录"""
    session_id = request.args.get("sessionId")
    if not session_id:
        return jsonify({"error": "缺少参数：sessionId"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "数据库不可用"}), 503
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, role, content, user_agent, created_at
            FROM chat_logs
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,)
        )
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 转换为 JSON 友好格式
        result = []
        for log in logs:
            result.append({
                "id": log["id"],
                "session_id": str(log["session_id"]),
                "role": log["role"],
                "content": log["content"],
                "user_agent": log["user_agent"],
                "created_at": log["created_at"].isoformat()
            })
        
        return jsonify({
            "success": True,
            "count": len(result),
            "logs": result
        }), 200
        
    except Exception as e:
        logger.error(f"查询对话日志失败: {e}")
        if conn:
            conn.close()
        return jsonify({"error": "查询失败"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
