[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$InputPath = "",

    [Parameter(Mandatory = $false)]
    [string]$OutputPath = "",

    [Parameter(Mandatory = $false)]
    [switch]$BuildOnly
)

$ErrorActionPreference = "Stop"
$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ToolRoot)
$Dotnet = Join-Path $RepoRoot "tools\dotnet\dotnet.exe"
$Project = Join-Path $ToolRoot "src\SafeEplExtractor\SafeEplExtractor.csproj"
$Upstream = Join-Path $ToolRoot "upstream\EProjectFile\EProjectFile\EProjectFile.csproj"
$RuntimeRoot = Join-Path $ToolRoot ".runtime"

if (-not (Test-Path -LiteralPath $Dotnet -PathType Leaf)) {
    throw "Portable .NET SDK not found: $Dotnet"
}
if (-not (Test-Path -LiteralPath $Upstream -PathType Leaf)) {
    throw "EProjectFile submodule is missing. Run: git submodule update --init tools/epl-source-recovery/upstream/EProjectFile"
}

$env:DOTNET_CLI_HOME = Join-Path $RuntimeRoot "dotnet-home"
$env:NUGET_PACKAGES = Join-Path $RuntimeRoot "nuget"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_NOLOGO = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_MULTILEVEL_LOOKUP = "0"

New-Item -ItemType Directory -Path $env:DOTNET_CLI_HOME -Force | Out-Null
New-Item -ItemType Directory -Path $env:NUGET_PACKAGES -Force | Out-Null

& $Dotnet build $Project --configuration Release --nologo
if ($LASTEXITCODE -ne 0) {
    throw "Safe EPL extractor build failed with exit code $LASTEXITCODE"
}
if ($BuildOnly) {
    return
}

if ([string]::IsNullOrWhiteSpace($InputPath)) {
    throw "InputPath is required unless BuildOnly is set."
}

$ResolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$Extension = [System.IO.Path]::GetExtension($ResolvedInput).ToLowerInvariant()
if ($Extension -notin @(".e", ".ec")) {
    throw "Unsupported EPL source extension: $Extension"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $Parent = Split-Path -Parent $ResolvedInput
    $Name = [System.IO.Path]::GetFileNameWithoutExtension($ResolvedInput)
    $OutputPath = Join-Path $Parent ($Name + ".epl-extracted")
}
$ResolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Path $ResolvedOutput -Force | Out-Null

$Extractor = Join-Path $ToolRoot "src\SafeEplExtractor\bin\Release\net10.0\SafeEplExtractor.dll"
& $Dotnet $Extractor $ResolvedInput $ResolvedOutput
if ($LASTEXITCODE -ne 0) {
    throw "Safe EPL extractor failed with exit code $LASTEXITCODE"
}
