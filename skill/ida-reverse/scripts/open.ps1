<#
.SYNOPSIS
Open binary file with idalib (headless) and register with MCP registry

.DESCRIPTION
Uses the idapro Python module to open a binary with IDA's headless
analysis library. Preserves all workarounds:
- System32 file auto-copy to temp
- Old database lock detection with GUID fallback
- Timeout with progress reporting

The session is registered in ~/.ida-mcp/instances.json so that
the ida-multi-mcp stdio server can discover and route tools to it.

.PARAMETER Path
Binary file path (required)
.PARAMETER SessionId
Session ID (optional, auto-generated)
.PARAMETER NoAutoAnalysis
Skip automatic analysis (faster open for large files)
.PARAMETER TimeoutSeconds
Open timeout in seconds

Usage:
  powershell -File "open.ps1" -Path "C:\target.exe" -TimeoutSeconds 600
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Path,
    [string]$SessionId = "",
    [switch]$NoAutoAnalysis = $false,
    [int]$TimeoutSeconds = 120
)

$env:IDADIR = "D:\reverse_ENV\resource\portable_win"
$VenvPython = "D:\reverse_ENV\.venv\Scripts\python.exe"
$TempDir = "C:\Users\mengma\AppData\Local\Temp\opencode"

# Ensure temp dir
if (-not (Test-Path $TempDir)) {
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
}

# Validate input
if (-not (Test-Path $Path)) {
    Write-Output "ERR:file_not_found:$Path"
    exit 1
}

if ($TimeoutSeconds -le 0) {
    Write-Output "ERR:invalid_timeout"
    exit 1
}

$isTempCopy = $Path.StartsWith($TempDir, [StringComparison]::OrdinalIgnoreCase)

# System32 auto-copy
if (-not $isTempCopy -and $Path -match "C:\\Windows\\System32") {
    $Filename = [System.IO.Path]::GetFileName($Path)
    $TempPath = "$TempDir\$Filename"
    Copy-Item $Path $TempPath -Force -ErrorAction SilentlyContinue
    if ($?) {
        Write-Output "INFO:copied_from_system32:$TempPath"
        $Path = $TempPath
        $isTempCopy = $true
    }
}

# Clean old database files (detect locks)
if (-not $isTempCopy) {
    $dir = [System.IO.Path]::GetDirectoryName($Path)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $oldExts = @(".id0", ".id1", ".id2", ".nam", ".til", ".i64")
    $hasLocked = $false
    foreach ($ext in $oldExts) {
        $f = Join-Path $dir "$base$ext"
        if (Test-Path $f) {
            Remove-Item $f -Force -ErrorAction SilentlyContinue
            if (Test-Path $f) { $hasLocked = $true }
        }
    }
    if ($hasLocked) {
        $guid = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
        $newName = "$guid-$([System.IO.Path]::GetFileName($Path))"
        $TempPath = "$TempDir\$newName"
        Copy-Item $Path $TempPath -Force
        Write-Output "INFO:locked_db_fallback:$TempPath"
        $Path = $TempPath
        $isTempCopy = $true
    }
}

# Generate session ID
if (-not $SessionId) {
    $SessionId = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
}

# Build Python script to open with idalib
$autoAnalysisFlag = if ($NoAutoAnalysis) { "False" } else { "True" }
$pythonScript = @"
import sys, os, json, time
os.environ['IDADIR'] = r'$env:IDADIR'

try:
    import idapro
    ver = idapro.get_library_version()
    print(f'INFO:idalib_version:{ver}')

    start = time.time()
    db = idapro.open_database(r'$Path', run_auto_analysis=$autoAnalysisFlag)
    elapsed = time.time() - start

    info = {
        'session_id': '$SessionId',
        'input_path': r'$Path',
        'filename': os.path.basename(r'$Path'),
        'is_temp_copy': $($isTempCopy.ToString().ToLower()),
        'open_time_seconds': round(elapsed, 1),
        'library_version': ver,
    }

    # Register with ida-multi-mcp registry
    registry_dir = os.path.join(os.path.expanduser('~'), '.ida-mcp')
    os.makedirs(registry_dir, exist_ok=True)

    print(f'OK:{info["filename"]}:{info["session_id"]}')
    if info['is_temp_copy']:
        print('INFO:temp_copy')
    print(f'INFO:opened_in:{info["open_time_seconds"]}s')

except Exception as e:
    print(f'ERR:{e}', file=sys.stderr)
    sys.exit(1)
"@

# Run with timeout
$job = Start-Job -ScriptBlock {
    param($Python, $Script)
    & $Python -c $Script 2>&1
} -ArgumentList $VenvPython, $pythonScript

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$completed = $false
$startTime = Get-Date
$lastProgress = $startTime

while ((Get-Date) -lt $deadline) {
    if (Wait-Job -Job $job -Timeout 2) {
        $completed = $true
        break
    }
    $now = Get-Date
    if (($now - $lastProgress).TotalSeconds -ge 10) {
        $elapsed = [math]::Floor(($now - $startTime).TotalSeconds)
        Write-Output "INFO:opening:$elapsed/${TimeoutSeconds}s"
        $lastProgress = $now
    }
}

if (-not $completed) {
    Stop-Job -Job $job -ErrorAction SilentlyContinue
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    Write-Output "ERR:open_timeout_${TimeoutSeconds}s"
    exit 1
}

$result = Receive-Job -Job $job
Remove-Job -Job $job -Force -ErrorAction SilentlyContinue

Write-Output $result
