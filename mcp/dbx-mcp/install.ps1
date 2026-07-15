$ErrorActionPreference = "Stop"

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$node = [IO.Path]::GetFullPath((Join-Path $repoRoot "tools\node22\node.exe"))
$npm = [IO.Path]::GetFullPath((Join-Path $repoRoot "tools\node22\npm.cmd"))
$lockFile = Join-Path $PSScriptRoot "package-lock.json"
$cacheRoot = Join-Path $PSScriptRoot ".npm-cache"
$prebuildCache = Join-Path $cacheRoot "_prebuilds"
$nodeHome = Split-Path -Parent $node
$gh = [IO.Path]::GetFullPath((Join-Path $repoRoot "tools\gh\bin\gh.exe"))
$curl = [IO.Path]::GetFullPath("C:\Windows\System32\curl.exe")
$serverEntry = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "node_modules\@dbx-app\mcp-server\dist\index.js"))

foreach ($path in @($node, $npm, $lockFile)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file is missing: $path"
    }
}

$nodeVersion = (& $node -p "process.versions.node").Trim()
$nodeAbi = (& $node -p "process.versions.modules").Trim()
$platformArch = (& $node -p "process.platform + '/' + process.arch").Trim()
if ([version]$nodeVersion -lt [version]"22.13.0" -or [version]$nodeVersion -ge [version]"23.0.0") {
    throw "DBX MCP requires the isolated Node 22 runtime; current version: $nodeVersion"
}
if ($platformArch -ne "win32/x64") {
    throw "This installer currently pins Windows x64 prebuilds; current platform: $platformArch"
}

$runningServers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "node.exe" -and
    $_.ExecutablePath -eq $node -and
    $_.CommandLine -and
    $_.CommandLine.IndexOf($serverEntry, [StringComparison]::OrdinalIgnoreCase) -ge 0
}
if ($runningServers) {
    $pids = ($runningServers | Select-Object -ExpandProperty ProcessId) -join ", "
    throw "DBX MCP is running (PID: $pids). Stop the project MCP process before reinstalling so native addons are not locked."
}

$lockReader = Join-Path $PSScriptRoot "lock-versions.mjs"
if (-not (Test-Path -LiteralPath $lockReader)) {
    throw "Lock reader is missing: $lockReader"
}
$versionsJson = & $node $lockReader $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "package-lock.json parsing failed with exit code $LASTEXITCODE"
}
$versions = $versionsJson | ConvertFrom-Json
$betterSqliteVersion = $versions.betterSqlite
$keytarVersion = $versions.keytar
if (-not $betterSqliteVersion -or -not $keytarVersion) {
    throw "Native dependency versions are missing from package-lock.json"
}

New-Item -ItemType Directory -Force -Path $prebuildCache | Out-Null
$env:npm_config_cache = $cacheRoot
$env:PATH = "$nodeHome;$env:PATH"

function Add-Prebuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Repository,
        [Parameter(Mandatory = $true)]
        [string]$Tag,
        [Parameter(Mandatory = $true)]
        [string]$AssetName,
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    $sha = [Security.Cryptography.SHA512]::Create()
    try {
        $digest = ([BitConverter]::ToString(
            $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Url))
        )).Replace("-", "").ToLowerInvariant().Substring(0, 6)
    }
    finally {
        $sha.Dispose()
    }

    $cacheAssetName = $AssetName -replace "[^a-zA-Z0-9.]+", "-"
    $destination = Join-Path $prebuildCache "$digest-$cacheAssetName"
    if ((Test-Path -LiteralPath $destination) -and (Get-Item -LiteralPath $destination).Length -gt 100000) {
        Write-Output "Prebuild cache hit: $AssetName"
        return
    }

    $partial = "$destination.part"
    $downloadDir = Join-Path $cacheRoot "downloads"
    $downloaded = Join-Path $downloadDir $AssetName
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    if (Test-Path -LiteralPath $partial) {
        Remove-Item -LiteralPath $partial -Force
    }

    if (Test-Path -LiteralPath $gh) {
        Write-Output "Downloading prebuild through GitHub CLI: $AssetName"
        & $gh release download $Tag --repo $Repository --pattern $AssetName --dir $downloadDir --clobber
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $downloaded) -and (Get-Item -LiteralPath $downloaded).Length -gt 100000) {
            Move-Item -LiteralPath $downloaded -Destination $destination -Force
            return
        }
    }

    if (-not (Test-Path -LiteralPath $curl)) {
        throw "curl.exe is missing: $curl"
    }
    Write-Output "Downloading prebuild through curl: $AssetName"
    & $curl -L --fail --retry 8 --retry-all-errors --connect-timeout 15 `
        --speed-limit 1 --speed-time 45 --continue-at - --output $partial $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Prebuild download failed: $AssetName"
    }
    if ((Get-Item -LiteralPath $partial).Length -le 100000) {
        throw "Prebuild asset is unexpectedly small: $partial"
    }
    Move-Item -LiteralPath $partial -Destination $destination -Force
}

$betterSqliteUrl = "https://github.com/WiseLibs/better-sqlite3/releases/download/v$betterSqliteVersion/better-sqlite3-v$betterSqliteVersion-node-v$nodeAbi-win32-x64.tar.gz"
$keytarUrl = "https://github.com/atom/node-keytar/releases/download/v$keytarVersion/keytar-v$keytarVersion-napi-v3-win32-x64.tar.gz"
$betterSqliteAsset = "better-sqlite3-v$betterSqliteVersion-node-v$nodeAbi-win32-x64.tar.gz"
$keytarAsset = "keytar-v$keytarVersion-napi-v3-win32-x64.tar.gz"
Add-Prebuild -Repository "WiseLibs/better-sqlite3" -Tag "v$betterSqliteVersion" -AssetName $betterSqliteAsset -Url $betterSqliteUrl
Add-Prebuild -Repository "atom/node-keytar" -Tag "v$keytarVersion" -AssetName $keytarAsset -Url $keytarUrl

Push-Location $PSScriptRoot
try {
    & $npm ci --registry="https://registry.npmjs.org" --foreground-scripts
    if ($LASTEXITCODE -ne 0) {
        throw "npm ci failed with exit code $LASTEXITCODE"
    }

    & $node -e "require('better-sqlite3'); require('keytar'); console.log('native addons OK')"
    if ($LASTEXITCODE -ne 0) {
        throw "Native addon load check failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Output "DBX MCP dependencies installed with Node $nodeVersion (ABI $nodeAbi)."
