#requires -Version 5.1

<#
.SYNOPSIS
List all LDPlayer instances with RE project annotations.

.DESCRIPTION
Shows index, name, status, ADB address, resolution for every instance.
Highlights: [MAA] for index 0, [RE] for project instances, [ORPHAN] for unnamed.

Usage:
  powershell -File "re-list.ps1"
  powershell -File "re-list.ps1" -Project myapp    # show one project
#>

[CmdletBinding()]
param(
    [string]$Project
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── Paths ──────────────────────────────────────────────────────────
$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'
$AdbExe    = 'D:\leidian\LDPlayer9\adb.exe'

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
            Width   = $parts[7]
            Height  = $parts[8]
            Dpi     = $parts[9]
            Adb     = "emulator-$([int]$parts[0] * 2 + 5554)"
        }
    }
    return $instances | Sort-Object Index
}

# ── Main ───────────────────────────────────────────────────────────

$instances = Get-Instances

if ($Project) {
    $instances = $instances | Where-Object { $_.Name -eq $Project }
    if (-not $instances) {
        Write-Output "No instance found for project '$Project'."
        Write-Output "Create one: re-init.ps1 -Project $Project"
        exit 1
    }
}

if (-not $instances) {
    Write-Output 'No LDPlayer instances found.'
    Write-Output 'Create your first RE instance: re-init.ps1 -Project <name>'
    exit 0
}

# Classify instances
$classified = $instances | ForEach-Object {
    $type = if ($_.Index -eq 0) { 'MAA' }
            elseif ($_.Name -and $_.Name -ne '') { 'RE' }
            else { 'ORPHAN' }
    $_ | Add-Member -NotePropertyName Type -NotePropertyValue $type -PassThru
}

# Counts
$maaCount    = ($classified | Where-Object Type -eq 'MAA').Count
$reCount     = ($classified | Where-Object Type -eq 'RE').Count
$orphanCount = ($classified | Where-Object Type -eq 'ORPHAN').Count

Write-Output ''
Write-Output "=== LDPlayer Instances ($($classified.Count) total: $maaCount MAA, $reCount RE, $orphanCount orphan) ==="
Write-Output ''

# Header
$header = "{0,-6} {1,-6} {2,-18} {3,-8} {4,-18} {5,-14} {6}" -f 'Type', 'Index', 'Name', 'Status', 'ADB', 'Resolution', 'Note'
Write-Output $header
Write-Output ('─' * 90)

foreach ($i in $classified) {
    $status = if ($i.Running) { 'RUNNING' } else { 'STOPPED' }
    $res    = "$($i.Width)x$($i.Height)@$($i.Dpi)dpi"
    $note   = ''

    switch ($i.Type) {
        'MAA'    { $note = 'DO NOT TOUCH' }
        'ORPHAN' { $note = 'unnamed — safe to remove' }
        'RE'     { $note = "project: $($i.Name)" }
    }

    $line = "{0,-6} {1,-6} {2,-18} {3,-8} {4,-18} {5,-14} {6}" -f "[$($i.Type)]", $i.Index, $i.Name, $status, $i.Adb, $res, $note
    Write-Output $line
}

Write-Output ''
Write-Output 'Commands:'
Write-Output '  re-init.ps1    -Project <name>    create & launch project instance'
Write-Output '  re-proxy.ps1   -Project <name>     proxy on/off for project'
Write-Output '  re-destroy.ps1 -Project <name>    stop & remove project instance'
Write-Output ''
