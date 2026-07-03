#!/usr/bin/env node
/**
 * ruyi-mcp — Firefox 反检测浏览器全链路逆向 MCP 服务。
 *
 * 双场景架构：
 *   - 弱检测/无反检测 → js-reverse-mcp (Chrome/CDP)
 *   - 强检测 (CF/hCaptcha) → ruyi-mcp (Firefox/BiDi, 本服务)
 *
 * 工作流（对齐 mcp-js-reverse-playbook）:
 *   Observe → Capture → Rebuild → Patch → DeepDive
 *
 * 启动方式：
 *   node build/src/index.js
 *   或通过 .mcp.json 由 Claude Code 自动拉起
 */

import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';
import { PythonBridge } from './bridge/python.js';

async function main(): Promise<void> {
  console.error('[ruyi-mcp] Starting ruyi-mcp v0.1.0...');
  console.error('[ruyi-mcp] Browser: Firefox 151.0a1 (ruyipage)');
  console.error('[ruyi-mcp] Protocol: WebDriver BiDi');
  console.error('[ruyi-mcp] Anti-detection: 22-dim fingerprint + human simulation');
  console.error('[ruyi-mcp] Trace: BiDi events + ruyitrace DOM API hooks');

  const bridge = new PythonBridge();

  // Ensure bridge is stopped on exit
  process.on('exit', () => {
    bridge.stop().catch(() => {});
  });
  process.on('SIGINT', () => {
    console.error('[ruyi-mcp] SIGINT received');
    bridge.stop().catch(() => {});
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    console.error('[ruyi-mcp] SIGTERM received');
    bridge.stop().catch(() => {});
    process.exit(0);
  });

  try {
    const server = await createServer(bridge);
    const transport = new StdioServerTransport();

    console.error('[ruyi-mcp] Connecting to MCP transport...');
    await server.connect(transport);

    console.error('[ruyi-mcp] Ready. Waiting for MCP requests...');
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[ruyi-mcp] Fatal: ${message}`);
    await bridge.stop().catch(() => {});
    process.exit(1);
  }
}

main();
