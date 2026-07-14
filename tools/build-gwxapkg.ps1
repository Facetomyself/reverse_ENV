[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ToolsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ToolsRoot
$SourceDir = Join-Path $ToolsRoot 'Gwxapkg'
$RuntimeDir = Join-Path $ToolsRoot 'Gwxapkg-runtime'
$OutputExe = Join-Path $RuntimeDir 'gwxapkg.exe'
$GoExe = Join-Path $ToolsRoot 'go\bin\go.exe'

$resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedTools = (Resolve-Path -LiteralPath $ToolsRoot).Path
if (-not $resolvedTools.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Tools path is outside repository: $resolvedTools"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'go.mod'))) {
    throw "Gwxapkg submodule is missing or uninitialized: $SourceDir"
}
if (-not (Test-Path -LiteralPath $GoExe)) {
    throw "Project Go runtime is missing: $GoExe"
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
Push-Location $SourceDir
try {
    & $GoExe build -buildvcs=false -trimpath -ldflags '-s -w' -o $OutputExe .
    if ($LASTEXITCODE -ne 0) {
        throw "Gwxapkg build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$sourceCommit = (& git -C $SourceDir rev-parse HEAD).Trim()
$version = (& git -C $SourceDir describe --tags --always).Trim()
$info = [ordered]@{
    source_commit = $sourceCommit
    version = $version
    executable = $OutputExe
    sha256 = (Get-FileHash -LiteralPath $OutputExe -Algorithm SHA256).Hash.ToLowerInvariant()
    built_at = [DateTime]::UtcNow.ToString('o')
}
$json = $info | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText(
    (Join-Path $RuntimeDir 'build-info.json'),
    $json + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Gwxapkg runtime built: $OutputExe"
Write-Host "SHA256: $($info.sha256)"
