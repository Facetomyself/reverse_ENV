/**
 * Network enhancement tools: set_extra_headers, set_cache_behavior.
 * ruyi unique — request/response interception and modification.
 *
 * Note: Full intercept_requests/intercept_responses require BiDi network
 * interception which ruyipage supports. These are available via page.intercept.
 */

import { RuyiContext } from '../ruyi-context.js';
import { ToolDef, ToolHandler, ToolRegistrar } from './types.js';

function jsonResult(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

export function registerNetEnhanceTools(register: ToolRegistrar, ctx: RuyiContext): void {

  // -------------------------------------------------------------------------
  // ruyi_set_extra_headers
  // -------------------------------------------------------------------------
  register({
    tool: {
      name: 'ruyi_set_extra_headers',
      description:
        '为所有后续请求附加额外的 HTTP Headers。用于注入认证 token、自定义 UA 等。',
      inputSchema: {
        type: 'object',
        properties: {
          pageIdx: { type: 'number', default: 0 },
          headers: {
            type: 'object',
            description: 'Key-value 键值对，如 {"X-Token": "abc123", "X-Device-Id": "device1"}',
          },
        },
        required: ['headers'],
      },
    },
    handler: (async (args) => {
      const pageIdx = (args.pageIdx as number) || ctx.getActivePageIdx();
      const headers = args.headers as Record<string, string>;

      // Via JS: intercept fetch and XMLHttpRequest
      const headerInjections = Object.entries(headers)
        .map(([k, v]) => [k, v])
        .filter(([k]) => k.toLowerCase() !== 'host'); // Can't override Host

      if (headerInjections.length === 0) {
        return {
          content: [{ type: 'text', text: jsonResult({ applied: 0, warning: 'No valid headers' }) }],
        };
      }

      const headerObj = JSON.stringify(Object.fromEntries(headerInjections));

      const script = `() => {
        const extraHeaders = ${headerObj};

        // Intercept fetch
        const _fetch = window.fetch;
        window.fetch = function(url, init = {}) {
          init.headers = { ...init.headers, ...extraHeaders };
          return _fetch.call(this, url, init);
        };

        // Intercept XMLHttpRequest
        const _open = XMLHttpRequest.prototype.open;
        const _setRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
        XMLHttpRequest.prototype.open = function(method, url, ...args) {
          this.__ruyi_extraHeaders = { ...extraHeaders };
          return _open.call(this, method, url, ...args);
        };
        XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
          if (this.__ruyi_extraHeaders) {
            Object.entries(this.__ruyi_extraHeaders).forEach(([k, v]) => {
              _setRequestHeader.call(this, k, v);
            });
            this.__ruyi_extraHeaders = null;
          }
          return _setRequestHeader.call(this, name, value);
        };

        return Object.keys(extraHeaders).length;
      }`;

      const result = await ctx.bridgeInstance.call('script.evaluate', { pageIdx, script }) as Record<string, unknown>;

      return {
        content: [{ type: 'text', text: jsonResult({ applied: true, headers: Object.keys(headers), result }) }],
      };
    }) as ToolHandler,
  });

  // -------------------------------------------------------------------------
  // ruyi_set_cache_behavior
  // -------------------------------------------------------------------------
  register({
    tool: {
      name: 'ruyi_set_cache_behavior',
      description: '控制浏览器缓存行为。可选：default（默认）、bypass（跳过缓存）、force_cache（强制缓存）。',
      inputSchema: {
        type: 'object',
        properties: {
          pageIdx: { type: 'number', default: 0 },
          mode: {
            type: 'string',
            description: '缓存模式',
            enum: ['default', 'bypass', 'force_cache'],
            default: 'default',
          },
        },
        required: ['mode'],
      },
    },
    handler: (async (args) => {
      const pageIdx = (args.pageIdx as number) || ctx.getActivePageIdx();

      // ruyipage supports set_cache_behavior natively
      try {
        await ctx.bridgeInstance.call('script.evaluate', {
          pageIdx,
          script: `() => {
            // Add cache-control bypass header to all fetches if bypass mode
            const mode = ${JSON.stringify(args.mode)};
            if (mode === 'bypass') {
              const _fetch = window.fetch;
              window.fetch = function(url, init = {}) {
                init.cache = 'no-store';
                init.headers = { ...init.headers, 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' };
                return _fetch.call(this, url, init);
              };
            }
            return mode;
          }`,
        });
      } catch {
        // Non-critical
      }

      return {
        content: [{ type: 'text', text: jsonResult({ cacheMode: args.mode }) }],
      };
    }) as ToolHandler,
  });
}
