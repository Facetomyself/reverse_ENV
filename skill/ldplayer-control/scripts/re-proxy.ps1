#requires -Version 5.1

<#
.SYNOPSIS
Enable/disable HTTPS interception proxy for a project instance.

.DESCRIPTION
Resolves project name to instance index, then delegates to ldplayer.ps1
proxy-on / proxy-off. Flow file is saved to workspace\<Project>\.

Setting up proxy involves:
  1. Push mitmproxy CA cert to instance
  2. Bind-mount cacerts directory (requires root)
  3. adb reverse proxy port
  4. Set Android global http_proxy
  5. Start mitmdump (if not already running)

Proxy-off reverses all of the above.

.PARAMETER Project
Project name — must match an existing instance name. (required)

.PARAMETER Action
'on' or 'off'. (required)

Usage:
  powershell -File "re-proxy.ps1" -Project myapp -Action on
  powershell -File "re-proxy.ps1" -Project myapp -Action off
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [ValidateSet('on', 'off')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── Paths ──────────────────────────────────────────────────────────
$LdConsole  = 'D:\leidian\LDPlayer9\ldconsole.exe'
$LdplayerPs1 = 'D:\reverse_ENV\tools\ldplayer\ldplayer.ps1'

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

# ── Resolve project → index ───────────────────────────────────────

$instances = Get-Instances
$target = $instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1

if (-not $target) {
    Write-Output "ERR: No instance named '$Project' found."
    Write-Output "  Available instances:"
    foreach ($i in $instances) {
        if ($i.Name) { Write-Output "    [$($i.Index)] $($i.Name)" }
    }
    Write-Output "  Create one: re-init.ps1 -Project $Project"
    exit 1
}

if (-not $target.Running) {
    Write-Output "ERR: Instance '$Project' (index $($target.Index)) is not running."
    Write-Output "  Launch it first: re-init.ps1 -Project $Project"
    exit 1
}

Write-Output "Project: $Project  →  Instance: [$($target.Index)] $($target.Name)"

# ── Delegate to ldplayer.ps1 ──────────────────────────────────────

$proxyAction = if ($Action -eq 'on') { 'proxy-on' } else { 'proxy-off' }

Write-Output "Running: ldplayer.ps1 -Action $proxyAction -Index $($target.Index) -Project $Project"
Write-Output ''

& powershell -NoProfile -File $LdplayerPs1 `
    -Action $proxyAction `
    -Index $target.Index `
    -Project $Project

$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Output ''
    Write-Output "Proxy $Action finished with exit code $exitCode"
}
