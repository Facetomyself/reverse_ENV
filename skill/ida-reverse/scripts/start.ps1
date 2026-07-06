<#
.SYNOPSIS
Verify IDA Pro MCP environment (venv, idalib, ida-multi-mcp)

.DESCRIPTION
In ida-multi-mcp v0.1.0+, the MCP server is stdio-based and managed
by the MCP client (launched via .mcp.json / Codex config). This script
verifies that the environment is correctly set up and idalib is functional.

Usage: run without parameters
#>

$env:IDADIR = "D:\reverse_ENV\resource\portable_win"
$VenvPython = "D:\reverse_ENV\.venv\Scripts\python.exe"
$VenvDir = "D:\reverse_ENV\.venv"

$ok = $true

# 1. Check venv
if (-not (Test-Path $VenvPython)) {
    Write-Output "ERR:venv_python_not_found:$VenvPython"
    $ok = $false
} else {
    Write-Output "OK:venv_python:$VenvPython"
}

# 2. Check IDADIR
if (-not (Test-Path "$env:IDADIR\ida.exe")) {
    Write-Output "ERR:ida_exe_not_found:$env:IDADIR"
    $ok = $false
} else {
    Write-Output "OK:idadir:$env:IDADIR"
}

# 3. Check ida-multi-mcp installed in venv
if ($ok) {
    $check = & $VenvPython -c "import ida_multi_mcp; print(ida_multi_mcp.__version__)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output "ERR:ida_multi_mcp_import_failed:$check"
        $ok = $false
    } else {
        Write-Output "OK:ida_multi_mcp:v$check"
    }
}

# 4. Check idapro (idalib) can import
if ($ok) {
    $check = & $VenvPython -c "import idapro; print(idapro.get_library_version())" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output "WARN:ida_pro_module_import_failed:$check"
        Write-Output "HINT:run: pip install %IDADIR%\idalib\python\idapro-*.whl"
        Write-Output "HINT:run: python %IDADIR%\idalib\python\py-activate-idalib.py -d %IDADIR%"
    } else {
        Write-Output "OK:idapro:$check"
    }
}

# 5. Check MCP config
$McpJson = "D:\reverse_ENV\.mcp.json"
if (-not (Test-Path $McpJson)) {
    Write-Output "WARN:mcp_json_missing:$McpJson"
} else {
    Write-Output "OK:mcp_json:$McpJson"
}

# 6. Clean up stale idalib worker processes from previous sessions
$stale = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -eq $VenvPython -and $_.CommandLine -match "idalib_worker"
}
if ($stale) {
    Write-Output "INFO:stale_workers:$($stale.Count)"
    $stale | ForEach-Object { taskkill /F /T /PID $_.Id 2>$null | Out-Null }
}

# Summary
if ($ok) {
    Write-Output "READY:ida-multi-mcp environment verified"
    Write-Output "NOTE:MCP server is stdio-managed by the client via .mcp.json / Codex config"
    Write-Output "NOTE:Use idalib_open MCP tool to open files; worker HTTP is internal implementation detail"
} else {
    Write-Output "ERR:environment_check_failed"
}
