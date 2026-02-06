# Chat API Documentation

## Current Status
The chat API is currently in upgrade mode (升级中), returning a static response for all messages.

## Future OpenAI Integration

### Setup Instructions

1. **Get OpenAI API Key**
   - Sign up at https://platform.openai.com/
   - Generate an API key from the API keys section

2. **Configure Environment Variable**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Deploy Options**

   #### Option A: Vercel Deployment
   ```bash
   # Install Vercel CLI
   npm install -g vercel
   
   # Add environment variable in Vercel dashboard or CLI
   vercel env add OPENAI_API_KEY
   
   # Deploy
   vercel
   ```

   #### Option B: Netlify Deployment
   ```bash
   # Install Netlify CLI
   npm install -g netlify-cli
   
   # Add environment variable
   netlify env:set OPENAI_API_KEY "your-api-key-here"
   
   # Deploy
   netlify deploy --prod
   ```

   #### Option C: Express.js Server
   ```javascript
   const express = require('express');
   const { handleChatRequest } = require('./api/chat');
   
   const app = express();
   app.use(express.json());
   
   app.post('/api/chat', handleChatRequest);
   
   app.listen(3000, () => {
     console.log('Server running on port 3000');
   });
   ```

4. **Enable OpenAI Integration**
   - Open `api/chat.js`
   - Uncomment the OpenAI API integration code (lines marked with TODO)
   - The code will automatically use OpenAI if `OPENAI_API_KEY` is configured

### API Endpoint

**URL:** `/api/chat`  
**Method:** `POST`  
**Content-Type:** `application/json`

#### Request Body
```json
{
  "message": "用户的问题"
}
```

#### Response
```json
{
  "reply": "AI的回复",
  "timestamp": "2025-01-28T12:00:00.000Z"
}
```

#### Error Response
```json
{
  "error": "错误信息",
  "reply": "升级中！"
}
```

### Frontend Integration

Update the `callOpenAI` function in `index.html`:

```javascript
async function callOpenAI(message) {
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: message })
    });
    const data = await response.json();
    return data.reply;
  } catch (error) {
    console.error('Error calling OpenAI API:', error);
    return '抱歉，服务暂时不可用。';
  }
}
```

Then update the `sendMessage` function to use it:
```javascript
// Replace the setTimeout block with:
const reply = await callOpenAI(message);
addMessage(reply, false);
chatSendBtn.disabled = false;
chatInput.focus();
```

### Customization

The system prompt can be customized in `api/chat.js`:
```javascript
{
  role: 'system',
  content: '你是安翔（Xiang An）的AI助手。安翔是GlintLab的研究科学家和团队负责人，专注于计算机视觉和多模态大模型研究。请根据他的背景信息回答用户问题。'
}
```

### Cost Considerations

- GPT-3.5-turbo: ~$0.002 per 1K tokens
- GPT-4: ~$0.03-0.06 per 1K tokens
- Consider implementing rate limiting to control costs

### Security Best Practices

1. **Never commit API keys** to the repository
2. **Use environment variables** for sensitive configuration
3. **Implement rate limiting** to prevent abuse
4. **Validate and sanitize** all user inputs
5. **Add authentication** if needed for production use

## Testing

Test the current implementation by typing any message in the chat box. It will respond with "升级中！"

Once OpenAI integration is enabled, the chat will provide intelligent responses based on the system prompt.
