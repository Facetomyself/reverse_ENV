#requires -Version 5.1

<#
.SYNOPSIS
Enable or disable HTTPS interception for one project LDPlayer instance.

.DESCRIPTION
Resolves project name to instance index, refuses index 0, and delegates to
tools\ldplayer\ldplayer.ps1. By default the proxy port is 8080 + instance index,
so multiple RE projects can run independently.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [ValidateSet('on', 'off')]
    [string]$Action,

    [int]$ProxyPort = 0
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'
$LdplayerPs1 = 'D:\reverse_ENV\tools\ldplayer\ldplayer.ps1'
$MaaIndex = 0

function Invoke-Ld {
    param([Parameter(Mandatory = $true)][string[]]$LdArgs)
    if (-not (Test-Path -LiteralPath $LdConsole)) {
        Write-Output "ERR:ldconsole_not_found:$LdConsole"
        exit 1
    }
    $out = & $LdConsole @LdArgs 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Output "ERR:ldconsole_failed:$code"
        if ($out) { Write-Output $out }
        exit $code
    }
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-Instances {
    $raw = Invoke-Ld -LdArgs @('list2')
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 10) { continue }
        $instances += [PSCustomObject]@{
            Index = [int]$parts[0]
            Name = $parts[1]
            Running = [int]$parts[4] -eq 1
        }
    }
    return @($instances)
}

if (-not (Test-Path -LiteralPath $LdplayerPs1)) {
    Write-Output "ERR:ldplayer_script_not_found:$LdplayerPs1"
    exit 1
}

$target = Get-Instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1
if (-not $target) {
    Write-Output "ERR:instance_not_found:$Project"
    Write-Output "  Create one: re-init.ps1 -Project $Project -Template re-xposed"
    exit 1
}
if ($target.Index -eq $MaaIndex) {
    Write-Output "ERR:project_resolves_to_index_0_MAA:$Project"
    exit 1
}
if ($Action -eq 'on' -and -not $target.Running) {
    Write-Output "ERR:instance_not_running:index=$($target.Index)"
    Write-Output "  Launch it first: re-init.ps1 -Project $Project"
    exit 1
}

if ($ProxyPort -le 0) {
    $ProxyPort = 8080 + [int]$target.Index
}

$proxyAction = if ($Action -eq 'on') { 'proxy-on' } else { 'proxy-off' }

Write-Output "Project: $Project -> instance [$($target.Index)] $($target.Name)"
Write-Output "ProxyPort: $ProxyPort"
Write-Output "Running: ldplayer.ps1 -Action $proxyAction -Index $($target.Index) -Project $Project -ProxyPort $ProxyPort"
Write-Output ''

& powershell -NoProfile -ExecutionPolicy Bypass -File $LdplayerPs1 `
    -Action $proxyAction `
    -Index $target.Index `
    -Project $Project `
    -ProxyPort $ProxyPort

exit $LASTEXITCODE
