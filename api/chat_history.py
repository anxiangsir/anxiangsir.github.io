"""
Chat History API service for storing and retrieving conversation records.
Uses Vercel Postgres database to persist chat history.
"""

import logging
import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 从环境变量获取数据库连接信息
# Vercel 会自动注入 POSTGRES_URL 等环境变量
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


@app.route("/api/chat_history", methods=["POST"])
def save_chat_history():
    """
    保存一条对话记录
    请求体: {
        "sessionId": "uuid-string",
        "role": "user" 或 "assistant",
        "content": "对话内容"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "无效的请求格式"}), 400
    
    session_id = data.get("sessionId")
    role = data.get("role")
    content = data.get("content")
    
    # 验证必填字段
    if not session_id or not role or not content:
        return jsonify({"error": "缺少必填字段：sessionId, role, content"}), 400
    
    # 验证 role 字段
    if role not in ["user", "assistant"]:
        return jsonify({"error": "role 必须是 'user' 或 'assistant'"}), 400
    
    # 连接数据库
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cursor = conn.cursor()
        
        # 插入对话记录
        cursor.execute(
            """
            INSERT INTO conversations (session_id, role, content)
            VALUES (%s, %s, %s)
            RETURNING id, created_at
            """,
            (session_id, role, content)
        )
        
        result = cursor.fetchone()
        record_id = result[0]
        created_at = result[1]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "id": record_id,
            "created_at": created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.exception("保存对话记录失败")
        if conn:
            conn.close()
        return jsonify({"error": "保存失败"}), 500


@app.route("/api/chat_history", methods=["GET"])
def get_chat_history():
    """
    获取某个会话的所有对话记录
    查询参数: sessionId (必填)
    返回: 按时间正序排列的对话记录列表
    """
    session_id = request.args.get("sessionId")
    
    if not session_id:
        return jsonify({"error": "缺少 sessionId 参数"}), 400
    
    # 连接数据库
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        cursor = conn.cursor()
        
        # 查询对话记录，按时间正序排列
        cursor.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM conversations
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,)
        )
        
        rows = cursor.fetchall()
        
        # 转换为 JSON 格式
        messages = []
        for row in rows:
            messages.append({
                "id": row[0],
                "sessionId": str(row[1]),
                "role": row[2],
                "content": row[3],
                "createdAt": row[4].isoformat()
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "sessionId": session_id,
            "messages": messages,
            "count": len(messages)
        }), 200
        
    except Exception as e:
        logger.exception("获取对话记录失败")
        if conn:
            conn.close()
        return jsonify({"error": "获取失败"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port)
