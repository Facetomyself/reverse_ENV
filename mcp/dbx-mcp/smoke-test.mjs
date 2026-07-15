import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const server = path.join(
  root,
  "node_modules",
  "@dbx-app",
  "mcp-server",
  "dist",
  "index.js",
);

const child = spawn(process.execPath, [server], {
  cwd: root,
  env: process.env,
  stdio: ["pipe", "pipe", "pipe"],
  windowsHide: true,
});

let stderr = "";
child.stderr.setEncoding("utf8");
child.stderr.on("data", (chunk) => {
  stderr += chunk;
});

const pending = new Map();
const output = createInterface({ input: child.stdout });
output.on("line", (line) => {
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    return;
  }
  if (message.id !== undefined && pending.has(message.id)) {
    const { resolve } = pending.get(message.id);
    pending.delete(message.id);
    resolve(message);
  }
});

function request(id, method, params = {}) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out waiting for ${method}. stderr=${stderr.trim()}`));
    }, 15_000);
    pending.set(id, {
      resolve(message) {
        clearTimeout(timer);
        resolve(message);
      },
    });
    child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
  });
}

try {
  const initialize = await request(1, "initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "reverse-env-dbx-smoke", version: "1.0.0" },
  });
  if (initialize.error) {
    throw new Error(`initialize failed: ${JSON.stringify(initialize.error)}`);
  }

  child.stdin.write(
    `${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" })}\n`,
  );
  const tools = await request(2, "tools/list");
  if (tools.error) {
    throw new Error(`tools/list failed: ${JSON.stringify(tools.error)}`);
  }

  const names = tools.result?.tools?.map((tool) => tool.name) ?? [];
  if (names.length !== 10 || names.some((name) => !name.startsWith("dbx_"))) {
    throw new Error(`Unexpected DBX tool set: ${JSON.stringify(names)}`);
  }

  const listConnections = await request(3, "tools/call", {
    name: "dbx_list_connections",
    arguments: {},
  });
  if (listConnections.error || listConnections.result?.isError) {
    throw new Error("dbx_list_connections returned an error");
  }

  process.stdout.write(
    `${JSON.stringify({ protocolVersion: initialize.result.protocolVersion, toolCount: names.length, listConnectionsOk: true, tools: names }, null, 2)}\n`,
  );
} finally {
  output.close();
  child.stdin.end();
  child.kill();
}
