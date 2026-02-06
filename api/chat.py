"""
Chat API service using Alibaba Cloud DashScope (Qwen model).
Reads the DASHSCOPE_API_KEY from environment variables (Repository secrets).
"""

import logging
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-flash"

SYSTEM_PROMPT = (
    "你是安翔（Xiang An）的AI助手。安翔是GlintLab的研究科学家和团队负责人，"
    "专注于计算机视觉和多模态大模型研究。请根据他的背景信息回答用户问题。"
)


def get_client():
    """Create and return an OpenAI-compatible client for DashScope."""
    if not DASHSCOPE_API_KEY:
        return None
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=BASE_URL)


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat requests."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("message"), str) or not data["message"].strip():
        return jsonify({"error": "无效的消息格式"}), 400

    client = get_client()
    if client is None:
        return jsonify({"error": "服务器错误", "reply": "抱歉，服务暂时不可用。"}), 500

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": data["message"].strip()},
            ],
        )
        reply = completion.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        logger.exception("Chat API error")
        return jsonify({"error": "服务器错误", "reply": "抱歉，服务暂时不可用。"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
