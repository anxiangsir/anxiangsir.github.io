const { spawn } = require('child_process');

const mcp = spawn('npx', ['@playwright/mcp@latest']);
mcp.stdout.on('data', data => {
  console.log(data.toString());
});
mcp.stderr.on('data', data => {
  console.error('stderr:', data.toString());
});

mcp.stdin.write(JSON.stringify({
  jsonrpc: "2.0",
  id: 1,
  method: "tools/list",
  params: {}
}) + '\n');

setTimeout(() => mcp.kill(), 3000);
