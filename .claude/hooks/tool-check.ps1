# tool-check.ps1 — Quick project tool availability check
# SessionStart hook: silent on success, reports only missing tools

$ErrorActionPreference = "Stop"
$missing = @()

$checks = @(
    @{ Name = "Python (venv)";     Path = "D:\reverse_ENV\.venv\Scripts\python.exe" },
    @{ Name = "Node.js";           Path = "D:\reverse_ENV\tools\node\node.exe" },
    @{ Name = "adb";               Path = "D:\reverse_ENV\tools\adb\adb.exe" },
    @{ Name = "jadx";              Path = "D:\reverse_ENV\tools\jadx\bin\jadx.bat" },
    @{ Name = "radare2";           Path = "D:\reverse_ENV\tools\radare2\bin\radare2.exe" },
    @{ Name = "frida";             Path = "D:\reverse_ENV\.venv\Scripts\frida.exe" },
    @{ Name = "IDA Pro (dir)";     Path = "D:\reverse_ENV\resource\portable_win" }
)

foreach ($c in $checks) {
    if (-not (Test-Path $c.Path)) {
        $missing += "$($c.Name): $($c.Path)"
    }
}

# ALWAYS print the WebFetch constraint — it's the #1 accidental violation
Write-Host ""
Write-Host "=== CONSTRAINT: WebFetch BLOCKED ===" -ForegroundColor Cyan
Write-Host "  DO NOT use WebFetch. Use global search-layer / content-extract / github-solution-research / browser MCP instead."
Write-Host "  search-layer is a global Claude MCP tier (WebSearch + Exa + Tavily + Grok), not a project .mcp.json server."
Write-Host "  See CLAUDE.md §任务前强制检查 for routing rules."
Write-Host ""

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "=== MISSING TOOLS ===" -ForegroundColor Yellow
    foreach ($m in $missing) {
        Write-Host "  [MISS] $m" -ForegroundColor Red
    }
    Write-Host "  Update CLAUDE.md tool table if paths have changed" -ForegroundColor DarkGray
    Write-Host ""
}

exit 0
