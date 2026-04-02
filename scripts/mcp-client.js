const { spawn } = require('child_process');

const mcp = spawn('npx', ['@playwright/mcp@latest'], {
  env: { ...process.env, PLAYWRIGHT_CHROMIUM_SANDBOX: '0' }
});

let messageId = 1;
const callbacks = {};
let buffer = '';

mcp.stdout.on('data', data => {
  buffer += data.toString();
  let lines = buffer.split('\n');
  buffer = lines.pop();
  
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const msg = JSON.parse(line);
      if (callbacks[msg.id]) {
        callbacks[msg.id](msg);
        delete callbacks[msg.id];
      }
    } catch(e) {
      console.error("Parse error:", e);
    }
  }
});

mcp.stderr.on('data', data => {
  console.error('stderr:', data.toString());
});

function callTool(name, args) {
  return new Promise(resolve => {
    const id = messageId++;
    callbacks[id] = resolve;
    mcp.stdin.write(JSON.stringify({
      jsonrpc: "2.0",
      id,
      method: "tools/call",
      params: { name, arguments: args }
    }) + '\n');
  });
}

async function run() {
  console.log("Navigating...");
  let res1 = await callTool('browser_navigate', { url: 'http://192.168.254.250:8000/' });
  console.log(JSON.stringify(res1));
  
  console.log("Waiting a bit...");
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("Taking screenshot...");
  let res2 = await callTool('browser_take_screenshot', { type: 'png', fullPage: true, filename: 'screenshot.png' });
  console.log(JSON.stringify(res2));
  
  mcp.kill();
}

run().catch(console.error);
