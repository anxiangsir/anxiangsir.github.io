// Backend API for Chat functionality
// This file is prepared for future OpenAI API integration

/**
 * Chat API endpoint
 * Currently returns "升级中！" for all messages
 * TODO: Integrate with OpenAI API
 */

// Environment configuration
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';
const OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions';

/**
 * Handle chat request
 * @param {Object} req - Request object containing user message
 * @param {Object} res - Response object
 */
async function handleChatRequest(req, res) {
  try {
    const { message } = req.body;
    
    if (!message || typeof message !== 'string') {
      return res.status(400).json({ 
        error: '无效的消息格式' 
      });
    }

    // Current implementation: Always return "升级中！"
    const reply = '升级中！';
    
    // TODO: Uncomment the following code when ready to integrate OpenAI API
    /*
    if (!OPENAI_API_KEY) {
      return res.status(500).json({ 
        error: 'OpenAI API key not configured',
        reply: '升级中！'
      });
    }

    const response = await fetch(OPENAI_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${OPENAI_API_KEY}`
      },
      body: JSON.stringify({
        model: 'gpt-3.5-turbo',
        messages: [
          {
            role: 'system',
            content: '你是安翔（Xiang An）的AI助手。安翔是GlintLab的研究科学家和团队负责人，专注于计算机视觉和多模态大模型研究。请根据他的背景信息回答用户问题。'
          },
          {
            role: 'user',
            content: message
          }
        ],
        temperature: 0.7,
        max_tokens: 500
      })
    });

    const data = await response.json();
    
    if (data.error) {
      throw new Error(data.error.message || 'OpenAI API error');
    }

    const reply = data.choices[0].message.content;
    */

    return res.status(200).json({ 
      reply: reply,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Chat API error:', error);
    return res.status(500).json({ 
      error: '服务器错误',
      reply: '升级中！'
    });
  }
}

// For serverless environments (e.g., Vercel, Netlify)
module.exports = async (req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle OPTIONS request
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Handle POST request
  if (req.method === 'POST') {
    return await handleChatRequest(req, res);
  }

  // Method not allowed
  return res.status(405).json({ error: 'Method not allowed' });
};

// For Express.js environments
module.exports.handleChatRequest = handleChatRequest;
