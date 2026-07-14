#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApkPath,

    [string]$Name,

    [string]$OutRoot,

    [switch]$SkipJadx,

    [switch]$SkipApktool,

    [switch]$NoDexChecksum,

    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# Auto-set JAVA_HOME if not already set (use bundled JDK 21)
if (-not $env:JAVA_HOME) {
    $bundledJdk = 'D:\reverse_ENV\tools\jdk'
    if (Test-Path $bundledJdk) {
        $env:JAVA_HOME = $bundledJdk
        $env:PATH = "$bundledJdk\bin;$env:PATH"
    }
}

function Get-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $fallbacks = @{
        'jadx' = @(
            'D:\reverse_ENV\tools\jadx.cmd',
            'D:\reverse_ENV\tools\jadx\bin\jadx.bat'
        )
        'apktool' = @(
            'D:\reverse_ENV\tools\apktool\apktool.bat'
        )
    }

    if ($fallbacks.Contains($Name)) {
        foreach ($candidate in $fallbacks[$Name]) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Missing required CLI tool: $Name"
}

function Get-SafeName {
    param([Parameter(Mandatory = $true)][string]$Value)

    $raw = [System.IO.Path]::GetFileNameWithoutExtension($Value)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        $raw = 'apk'
    }
    $safe = ($raw -replace '[^A-Za-z0-9._-]', '_').Trim('.', '-', '_')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        throw "Unable to derive a safe task name from: $Value"
    }
    return $safe
}

function Get-DefaultOutRoot {
    param([Parameter(Mandatory = $true)][string]$ApkFilePath)

    return 'D:\reverse_ENV\workspace'
}

function Get-ManifestPackage {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        return ''
    }

    try {
        $xml = [xml](Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8)
        return [string]$xml.manifest.package
    }
    catch {
        return ''
    }
}

if (-not (Test-Path -LiteralPath $ApkPath)) {
    throw "APK not found: $ApkPath"
}
if ($SkipJadx -and $SkipApktool) {
    throw 'Cannot skip both jadx and apktool.'
}
$ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path

$jadxPath = $null
$apktoolPath = $null

if (-not $SkipJadx) {
    $jadxPath = Get-ToolPath -Name 'jadx'
}
if (-not $SkipApktool) {
    $apktoolPath = Get-ToolPath -Name 'apktool'
}

$taskName = if ($Name) { Get-SafeName -Value $Name } else { Get-SafeName -Value $ApkPath }
$resolvedOutRoot = if ([string]::IsNullOrWhiteSpace($OutRoot)) { Get-DefaultOutRoot -ApkFilePath $ApkPath } else { $OutRoot }

if (-not (Test-Path -LiteralPath $resolvedOutRoot)) {
    New-Item -ItemType Directory -Path $resolvedOutRoot -Force | Out-Null
}
$resolvedOutRoot = (Resolve-Path -LiteralPath $resolvedOutRoot).Path
$taskRoot = Join-Path $resolvedOutRoot $taskName
$jadxOut = Join-Path $taskRoot 'jadx'
$apktoolOut = Join-Path $taskRoot 'apktool'
$summaryPath = Join-Path $taskRoot 'decode-summary.json'
$manifestSummaryPath = Join-Path $taskRoot 'manifest-summary.txt'

if (-not (Test-Path -LiteralPath $taskRoot)) {
    New-Item -ItemType Directory -Path $taskRoot -Force | Out-Null
}

if ($Clean) {
    # Only remove generated artifacts. Never delete the project root because
    # the source APK may live inside workspace\<project>.
    foreach ($generatedPath in @($jadxOut, $apktoolOut, $summaryPath, $manifestSummaryPath)) {
        if (Test-Path -LiteralPath $generatedPath) {
            Remove-Item -LiteralPath $generatedPath -Recurse -Force
        }
    }
}
else {
    $existingOutputs = @($jadxOut, $apktoolOut) | Where-Object { Test-Path -LiteralPath $_ }
    if ($existingOutputs.Count -gt 0) {
        throw "Generated output already exists; pass -Clean or choose another -Name: $($existingOutputs -join ', ')"
    }
}

$jadxExitCode = $null
if (-not $SkipJadx) {
    $jadxArgs = @('-d', $jadxOut)
    if ($NoDexChecksum) {
        $jadxArgs += '-Pdex-input.verify-checksum=no'
    }
    $jadxArgs += $ApkPath
    & $jadxPath @jadxArgs
    $jadxExitCode = $LASTEXITCODE
}

$apktoolExitCode = $null
if (-not $SkipApktool) {
    & $apktoolPath d $ApkPath -o $apktoolOut -f
    $apktoolExitCode = $LASTEXITCODE
}

$manifestPath = Join-Path $apktoolOut 'AndroidManifest.xml'
$packageName = if (-not $SkipApktool) { Get-ManifestPackage -ManifestPath $manifestPath } else { '' }
$javaCount = if ((Test-Path -LiteralPath $jadxOut)) { (Get-ChildItem -LiteralPath $jadxOut -Recurse -File -Filter '*.java' | Measure-Object).Count } else { 0 }
$smaliDirCount = if ((Test-Path -LiteralPath $apktoolOut)) { (Get-ChildItem -LiteralPath $apktoolOut -Directory -Filter 'smali*' | Measure-Object).Count } else { 0 }
$libCount = if ((Test-Path -LiteralPath $apktoolOut)) { (Get-ChildItem -LiteralPath $apktoolOut -Recurse -File -Filter '*.so' | Measure-Object).Count } else { 0 }
$resXmlCount = if ((Test-Path -LiteralPath $apktoolOut)) { (Get-ChildItem -LiteralPath $apktoolOut -Recurse -File -Filter '*.xml' | Measure-Object).Count } else { 0 }
$apkSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ApkPath).Hash
$packedSuspected = (-not $SkipJadx) -and ($javaCount -lt 50)
$jadxUsable = [bool]$SkipJadx -or $javaCount -gt 0
$apktoolUsable = [bool]$SkipApktool -or (Test-Path -LiteralPath $manifestPath) -or $smaliDirCount -gt 0 -or $resXmlCount -gt 0
$pipelineStatus = if ($jadxUsable -and $apktoolUsable) { 'success' } elseif ($jadxUsable -or $apktoolUsable) { 'partial' } else { 'failed' }

if (Test-Path -LiteralPath $manifestPath) {
    $manifestSummaryScript = Join-Path $PSScriptRoot 'manifest-summary.ps1'
    $manifestSummary = @(& $manifestSummaryScript -ManifestPath $manifestPath)
    $manifestSummaryText = ($manifestSummary -join "`n") + "`n"
    [System.IO.File]::WriteAllText($manifestSummaryPath, $manifestSummaryText, [System.Text.UTF8Encoding]::new($false))
}

$summary = [ordered]@{
    generated_at = [DateTimeOffset]::Now.ToString('o')
    apk_path = $ApkPath
    apk_sha256 = $apkSha256
    task_root = $taskRoot
    status = $pipelineStatus
    package = $packageName
    jadx = [ordered]@{
        skipped = [bool]$SkipJadx
        output = $jadxOut
        exit_code = $jadxExitCode
        java_files = $javaCount
        verify_checksum = -not [bool]$NoDexChecksum
    }
    apktool = [ordered]@{
        skipped = [bool]$SkipApktool
        output = $apktoolOut
        exit_code = $apktoolExitCode
        smali_dirs = $smaliDirCount
        so_files = $libCount
        xml_files = $resXmlCount
    }
    packed_suspected = $packedSuspected
    manifest_summary = if (Test-Path -LiteralPath $manifestSummaryPath) { $manifestSummaryPath } else { $null }
}
$summaryJson = ($summary | ConvertTo-Json -Depth 6) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText($summaryPath, $summaryJson + "`n", [System.Text.UTF8Encoding]::new($false))

"task_root=$taskRoot"
"status=$pipelineStatus"
"jadx_out=$jadxOut"
"apktool_out=$apktoolOut"
"package=$packageName"
"jadx_exit_code=$jadxExitCode"
"apktool_exit_code=$apktoolExitCode"
"java_files=$javaCount"
"smali_dirs=$smaliDirCount"
"so_files=$libCount"
"xml_files=$resXmlCount"
"packed_suspected=$packedSuspected"
"summary=$summaryPath"
if (Test-Path -LiteralPath $manifestSummaryPath) {
    "manifest_summary=$manifestSummaryPath"
}

if (($jadxExitCode -ne $null) -and ($jadxExitCode -ne 0)) {
    "warning=jadx returned non-zero exit code; inspect output but treat exported sources as usable if present"
}
if (($apktoolExitCode -ne $null) -and ($apktoolExitCode -ne 0)) {
    "warning=apktool returned non-zero exit code; inspect partial resources/smali before retrying"
}
if ($pipelineStatus -eq 'failed') {
    throw 'Both decode branches failed to produce usable artifacts. See decode-summary.json and tool output.'
}
