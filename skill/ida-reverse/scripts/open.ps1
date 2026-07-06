<#
.SYNOPSIS
Prepare a safe binary path for ida-multi-mcp idalib_open.

.DESCRIPTION
Compatibility helper only. It does not open the binary, does not write
~/.ida-mcp/instances.json, and does not bind an MCP session.

Use MCP idalib_open as the primary open path. This helper
only preserves path workarounds:
- System32 file auto-copy to temp
- Existing IDA database detection with non-destructive temp-copy fallback

The final READY_FOR_IDALIB_OPEN path should be passed to the MCP open tool.

.PARAMETER Path
Binary file path (required)
.PARAMETER CleanOldDb
Explicitly delete existing same-name IDA database files before returning the
original path. Default is false. Without this switch, existing database files
are never deleted; the binary is copied to temp with a GUID prefix instead.

Usage:
  powershell -File "open.ps1" -Path "C:\target.exe"
  powershell -File "open.ps1" -Path "C:\target.exe" -CleanOldDb
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Path,
    [switch]$CleanOldDb
)

$TempDir = Join-Path $env:TEMP "opencode"

if (-not (Test-Path -LiteralPath $TempDir)) {
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Output "ERR:file_not_found:$Path"
    exit 1
}

$resolved = (Resolve-Path -LiteralPath $Path).Path
$isTempCopy = $resolved.StartsWith($TempDir, [StringComparison]::OrdinalIgnoreCase)

if (-not $isTempCopy -and $resolved -match "^C:\\Windows\\System32\\") {
    $filename = [System.IO.Path]::GetFileName($resolved)
    $tempPath = Join-Path $TempDir $filename
    Copy-Item -LiteralPath $resolved -Destination $tempPath -Force -ErrorAction Stop
    Write-Output "INFO:copied_from_system32:$tempPath"
    $resolved = $tempPath
    $isTempCopy = $true
}

if (-not $isTempCopy) {
    $dir = [System.IO.Path]::GetDirectoryName($resolved)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($resolved)
    $oldExts = @(".id0", ".id1", ".id2", ".nam", ".til", ".i64")
    $oldDbFiles = @()

    foreach ($ext in $oldExts) {
        $candidate = Join-Path $dir "$base$ext"
        if (Test-Path -LiteralPath $candidate) {
            $oldDbFiles += $candidate
        }
    }

    if ($oldDbFiles.Count -gt 0) {
        Write-Output "WARN:old_db_exists:$($oldDbFiles -join ';')"
    }

    if ($oldDbFiles.Count -gt 0 -and $CleanOldDb) {
        $deleteFailed = $false
        foreach ($candidate in $oldDbFiles) {
            Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $candidate) {
                $deleteFailed = $true
            }
        }
        if ($deleteFailed) {
            Write-Output "WARN:old_db_delete_failed:using_temp_copy"
        } else {
            Write-Output "INFO:old_db_cleaned"
        }
    }

    if ($oldDbFiles.Count -gt 0 -and ((-not $CleanOldDb) -or $deleteFailed)) {
        $guid = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
        $newName = "$guid-$([System.IO.Path]::GetFileName($resolved))"
        $tempPath = Join-Path $TempDir $newName
        Copy-Item -LiteralPath $resolved -Destination $tempPath -Force -ErrorAction Stop
        Write-Output "INFO:old_db_temp_copy:$tempPath"
        $resolved = $tempPath
    }
}

Write-Output "READY_FOR_IDALIB_OPEN:$resolved"
Write-Output "NEXT:call MCP idalib_open/input_path with the READY_FOR_IDALIB_OPEN path"
