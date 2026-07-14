$ErrorActionPreference = "Stop"

$repoRoot = "D:\reverse_ENV"
$userCodex = Join-Path $env:USERPROFILE ".codex"

$checks = @(
    @{ Name = "Project MCP declaration"; Path = Join-Path $repoRoot ".mcp.json"; Required = $true },
    @{ Name = "Codex user config"; Path = Join-Path $userCodex "config.toml"; Required = $true },
    @{ Name = "Codex search-layer skill"; Path = Join-Path $userCodex "skills\search-layer\SKILL.md"; Required = $true },
    @{ Name = "Codex github-solution-research skill"; Path = Join-Path $userCodex "skills\github-solution-research\SKILL.md"; Required = $true },
    @{ Name = "Python venv"; Path = Join-Path $repoRoot ".venv\Scripts\python.exe"; Required = $true },
    @{ Name = "Node.js"; Path = Join-Path $repoRoot "tools\node\node.exe"; Required = $true },
    @{ Name = "ADB"; Path = Join-Path $repoRoot "tools\adb\adb.exe"; Required = $true },
    @{ Name = "radare2"; Path = Join-Path $repoRoot "tools\radare2\bin\radare2.exe"; Required = $true },
    @{ Name = "IDA Pro directory"; Path = Join-Path $repoRoot "resource\portable_win"; Required = $true },
    @{ Name = "ruyi-mcp submodule entry"; Path = Join-Path $repoRoot "mcp\ruyi-mcp\build\src\index.js"; Required = $true },
    @{ Name = "ruyi-mcp npm dependencies"; Path = Join-Path $repoRoot "mcp\ruyi-mcp\node_modules\@modelcontextprotocol\sdk\package.json"; Required = $true },
    @{ Name = "ruyi-mcp Firefox"; Path = Join-Path $repoRoot "tools\ruyitrace\firefox\firefox.exe"; Required = $true },
    @{ Name = "mitmdump"; Path = Join-Path $repoRoot ".venv\Scripts\mitmdump.exe"; Required = $false },
    @{ Name = "LDPlayer console"; Path = "D:\leidian\LDPlayer9\ldconsole.exe"; Required = $false },
    @{ Name = "LDPlayer adb"; Path = "D:\leidian\LDPlayer9\adb.exe"; Required = $false }
)

$missingRequired = New-Object System.Collections.Generic.List[string]
$missingOptional = New-Object System.Collections.Generic.List[string]

foreach ($check in $checks) {
    if (-not (Test-Path -LiteralPath $check.Path)) {
        $line = "{0}: {1}" -f $check.Name, $check.Path
        if ($check.Required) {
            $missingRequired.Add($line)
        } else {
            $missingOptional.Add($line)
        }
    }
}

Write-Host ""
Write-Host "=== reverse_ENV Codex preflight ===" -ForegroundColor Cyan
Write-Host "Policy: WebFetch blocked; use search-layer / github-solution-research / browser MCP routing."
Write-Host "Search discipline: new tasks/problems must run search-layer first, then github-solution-research for GitHub leads."
Write-Host "Search smoke: Codex search-layer deep mode verified with Exa + Tavily + Grok."
Write-Host "Layering: Claude and Codex both use global + project layers, but Codex project MCP belongs in .codex/config.toml, not .mcp.json."
Write-Host "MCP: reverse_ENV cold-start MCP is project-scoped: ida-multi-mcp + ruyi-mcp. GUI/SSE/client-bound MCPs stay on-demand."
Write-Host "Submodule: initialize ruyi-mcp, then run tools\node\npm.cmd --prefix mcp\ruyi-mcp ci."
Write-Host "Skills: search-layer is a Codex skill in the user skill layer, not a project .mcp.json server."

if ($missingRequired.Count -gt 0) {
    Write-Host ""
    Write-Host "=== MISSING REQUIRED CONTEXT ===" -ForegroundColor Yellow
    foreach ($item in $missingRequired) {
        Write-Host "  [MISS] $item" -ForegroundColor Red
    }
}

if ($missingOptional.Count -gt 0) {
    Write-Host ""
    Write-Host "=== OPTIONAL TOOLING NOT FOUND ===" -ForegroundColor DarkYellow
    foreach ($item in $missingOptional) {
        Write-Host "  [MISS] $item" -ForegroundColor DarkYellow
    }
}

Write-Host ""
exit 0
