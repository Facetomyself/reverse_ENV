#requires -Version 5.1

<#
.SYNOPSIS
Stop and optionally remove a reverse-engineering project instance.

.DESCRIPTION
Gracefully stops the instance, then optionally removes it.
Safety checks:
  - Refuses to touch index 0 (MAA)
  - Confirms before removal (unless -Force)

.PARAMETER Project
Project name — must match an existing instance name. (required)

.PARAMETER Remove
Also delete the instance (not just stop). Without this, only stops.

.PARAMETER Force
Skip confirmation prompts.

Usage:
  powershell -File "re-destroy.ps1" -Project myapp            # stop only
  powershell -File "re-destroy.ps1" -Project myapp -Remove     # stop & delete
  powershell -File "re-destroy.ps1" -Project myapp -Remove -Force  # no prompt
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [switch]$Remove,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── Paths ──────────────────────────────────────────────────────────
$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'

# ── Helpers ────────────────────────────────────────────────────────

function Invoke-Ld {
    param([string[]]$LdArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $LdConsole @LdArgs 2>$null
    $ErrorActionPreference = $prev
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-Instances {
    $raw = Invoke-Ld -LdArgs 'list2'
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 5) { continue }
        $instances += [PSCustomObject]@{
            Index   = [int]$parts[0]
            Name    = $parts[1]
            Running = [int]$parts[4] -eq 1
        }
    }
    return $instances
}

# ── Resolve ────────────────────────────────────────────────────────

$instances = Get-Instances
$target = $instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1

if (-not $target) {
    Write-Output "OK: Instance '$Project' does not exist — nothing to destroy."
    exit 0
}

# Safety: refuse MAA index
if ($target.Index -eq 0) {
    Write-Output "ERR: Instance '$Project' is index 0 (MAA) — refusing to touch."
    exit 1
}

Write-Output ''
Write-Output "=== Destroy: $Project (index $($target.Index)) ==="
Write-Output ''

# ── Stop ───────────────────────────────────────────────────────────

if ($target.Running) {
    Write-Output "Stopping instance '$Project'..."
    Invoke-Ld -LdArgs @('quit', '--name', $Project) | Out-Null
    Start-Sleep -Seconds 2

    # Verify stopped
    $check = Get-Instances | Where-Object { $_.Name -eq $Project }
    if ($check -and $check.Running) {
        Write-Output "WARN: Instance may still be running. Trying force quit..."
        Invoke-Ld -LdArgs @('quit', '--name', $Project) | Out-Null
        Start-Sleep -Seconds 3
    }
    Write-Output "  Stopped."
} else {
    Write-Output "Instance already stopped."
}

# ── Remove ─────────────────────────────────────────────────────────

if ($Remove) {
    if (-not $Force) {
        Write-Output ''
        Write-Output "WARNING: This will permanently delete instance '$Project' (index $($target.Index))."
        Write-Output "This action cannot be undone."
        Write-Output ''
        $confirm = Read-Host "Type '$Project' to confirm deletion"
        if ($confirm -ne $Project) {
            Write-Output "Deletion cancelled. (type '$Project' to confirm, got '$confirm')"
            exit 1
        }
    }

    Write-Output "Removing instance '$Project'..."
    Invoke-Ld -LdArgs @('remove', '--name', $Project) | Out-Null
    Start-Sleep -Seconds 2

    # Verify removed
    $check = Get-Instances | Where-Object { $_.Name -eq $Project }
    if (-not $check) {
        Write-Output "  Removed."
        Write-Output ''
        Write-Output "OK:destroyed — instance '$Project' has been deleted."
        Write-Output "  Workspace files in D:\reverse_ENV\workspace\$Project\ are untouched."
    } else {
        Write-Output "WARN: Instance may still exist. Check manually: ldconsole list2"
    }
} else {
    Write-Output ''
    Write-Output "OK:stopped — instance preserved."
    Write-Output "  To also delete: re-destroy.ps1 -Project $Project -Remove"
    Write-Output "  To restart:     re-init.ps1 -Project $Project"
}
