/**
 * Script analysis tools: list_scripts, get_script_source, save_script_source, search_in_sources.
 */
import { writeFileSync } from 'node:fs';
function jsonResult(data) {
    return JSON.stringify(data, null, 2);
}
export function registerScriptTools(register, ctx) {
    // -------------------------------------------------------------------------
    // ruyi_list_scripts
    // -------------------------------------------------------------------------
    register({
        tool: {
            name: 'ruyi_list_scripts',
            description: '列出页面中加载的所有 JavaScript 脚本 URL。支持 URL 筛选。',
            inputSchema: {
                type: 'object',
                properties: {
                    pageIdx: { type: 'number', default: 0 },
                    filter: { type: 'string', description: 'URL 筛选字符串（不区分大小写）' },
                },
                required: [],
            },
        },
        handler: (async (args) => {
            const pageIdx = args.pageIdx || ctx.getActivePageIdx();
            const filter = args.filter;
            let script = `() => {
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        return scripts.map(s => ({
          src: s.src,
          type: s.type || 'text/javascript',
          async: s.async,
          defer: s.defer,
        }));
      }`;
            if (filter) {
                script = `() => {
          const filter = ${JSON.stringify(filter)}.toLowerCase();
          const scripts = Array.from(document.querySelectorAll('script[src]'));
          return scripts
            .filter(s => s.src.toLowerCase().includes(filter))
            .map(s => ({
              src: s.src,
              type: s.type || 'text/javascript',
              async: s.async,
              defer: s.defer,
            }));
        }`;
            }
            const result = await ctx.bridgeInstance.call('script.evaluate', { pageIdx, script });
            return {
                content: [{ type: 'text', text: jsonResult(result) }],
            };
        }),
    });
    // -------------------------------------------------------------------------
    // ruyi_get_script_source
    // -------------------------------------------------------------------------
    register({
        tool: {
            name: 'ruyi_get_script_source',
            description: '获取指定 URL 脚本的源码片段。支持行号范围或字符偏移。',
            inputSchema: {
                type: 'object',
                properties: {
                    url: { type: 'string', description: '脚本 URL（精确匹配优先，然后子串匹配）' },
                    pageIdx: { type: 'number', default: 0 },
                    startLine: { type: 'number', description: '起始行号（1-based）' },
                    endLine: { type: 'number', description: '结束行号（1-based）' },
                    offset: { type: 'number', description: '字符偏移（0-based，用于单行压缩文件）' },
                    length: { type: 'number', description: '返回字符数（配合 offset 使用），默认 1000', default: 1000 },
                },
                required: ['url'],
            },
        },
        handler: (async (args) => {
            const pageIdx = args.pageIdx || ctx.getActivePageIdx();
            const url = args.url;
            // Fetch script content via fetch() + eval trick
            const script = `async () => {
        try {
          const resp = await fetch(${JSON.stringify(url)});
          const text = await resp.text();
          return text.substring(0, 50000);
        } catch(e) {
          return 'Error: ' + e.message;
        }
      }`;
            const result = await ctx.bridgeInstance.call('script.evaluate', {
                pageIdx,
                script,
                timeout: 15,
            });
            return {
                content: [{ type: 'text', text: jsonResult(result) }],
            };
        }),
    });
    // -------------------------------------------------------------------------
    // ruyi_save_script_source
    // -------------------------------------------------------------------------
    register({
        tool: {
            name: 'ruyi_save_script_source',
            description: '保存脚本完整源码到本地文件。JSON 结果用 .json 扩展名，其他用 .js。',
            inputSchema: {
                type: 'object',
                properties: {
                    url: { type: 'string', description: '脚本 URL' },
                    filePath: { type: 'string', description: '本地保存路径（绝对路径）' },
                    pageIdx: { type: 'number', default: 0 },
                },
                required: ['url', 'filePath'],
            },
        },
        handler: (async (args) => {
            const pageIdx = args.pageIdx || ctx.getActivePageIdx();
            const url = args.url;
            const filePath = args.filePath;
            const script = `async () => {
        try {
          const resp = await fetch(${JSON.stringify(url)});
          return await resp.text();
        } catch(e) {
          return 'Error: ' + e.message;
        }
      }`;
            const result = await ctx.bridgeInstance.call('script.evaluate', {
                pageIdx,
                script,
                timeout: 30,
            });
            const source = result.result || JSON.stringify(result);
            if (!source.startsWith('Error:')) {
                writeFileSync(filePath, source, 'utf-8');
                return {
                    content: [{ type: 'text', text: jsonResult({ savedTo: filePath, size: source.length }) }],
                };
            }
            return {
                content: [{ type: 'text', text: jsonResult({ error: source }) }],
            };
        }),
    });
    // -------------------------------------------------------------------------
    // ruyi_search_in_sources
    // -------------------------------------------------------------------------
    register({
        tool: {
            name: 'ruyi_search_in_sources',
            description: '在页面已加载的 JS 源码中搜索字符串或正则表达式。',
            inputSchema: {
                type: 'object',
                properties: {
                    query: { type: 'string', description: '搜索字符串或正则表达式' },
                    pageIdx: { type: 'number', default: 0 },
                    caseSensitive: { type: 'boolean', default: false },
                    isRegex: { type: 'boolean', default: false },
                    urlFilter: { type: 'string', description: '仅搜索 URL 含此字符串的脚本' },
                    maxResults: { type: 'number', description: '最大结果数，默认 30', default: 30 },
                },
                required: ['query'],
            },
        },
        handler: (async (args) => {
            const pageIdx = args.pageIdx || ctx.getActivePageIdx();
            const query = args.query;
            const isRegex = args.isRegex;
            const caseSensitive = args.caseSensitive;
            const urlFilter = args.urlFilter || '';
            const maxResults = args.maxResults || 30;
            // Search in all inline scripts and fetch-able external scripts
            const script = `async () => {
        const query = ${JSON.stringify(query)};
        const isRegex = ${isRegex};
        const caseSensitive = ${caseSensitive};
        const urlFilter = ${JSON.stringify(urlFilter)};
        const maxResults = ${maxResults};

        const results = [];
        const pattern = isRegex ? new RegExp(query, caseSensitive ? '' : 'i') : null;

        for (const el of document.querySelectorAll('script')) {
          const src = el.src || '(inline)';
          if (urlFilter && !src.toLowerCase().includes(urlFilter.toLowerCase())) continue;

          const text = el.textContent || '';
          if (text.length > 200000) continue; // skip huge scripts

          const lines = text.split('\\n');
          for (let i = 0; i < lines.length && results.length < maxResults; i++) {
            const line = lines[i];
            const matched = pattern
              ? pattern.test(line)
              : (caseSensitive ? line.includes(query) : line.toLowerCase().includes(query.toLowerCase()));
            if (matched) {
              results.push({
                src,
                line: i + 1,
                preview: line.substring(0, 200).trim(),
              });
            }
          }
        }

        return results;
      }`;
            const result = await ctx.bridgeInstance.call('script.evaluate', {
                pageIdx,
                script,
                timeout: 15,
            });
            return {
                content: [{ type: 'text', text: jsonResult(result) }],
            };
        }),
    });
}
//# sourceMappingURL=script.js.map