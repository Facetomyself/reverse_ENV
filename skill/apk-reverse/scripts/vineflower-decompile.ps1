[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputPath,

    [string]$OutputDir,

    [switch]$Clean,

    [switch]$KeepIntermediate,

    [switch]$RenameMembers
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$projectRoot = 'D:\reverse_ENV'
$javaPath = Join-Path $projectRoot 'tools\jdk\bin\java.exe'
$vineflowerPath = Join-Path $projectRoot 'tools\vineflower\vineflower-1.11.2.jar'
$dex2JarPath = Join-Path $projectRoot 'tools\dex2jar\dex-tools-2.4.31\d2j-dex2jar.bat'

function Test-IsWithinPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    return $fullPath.StartsWith(
        $fullRoot + '\',
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Assert-SafeOutputPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedInput
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowedRoots = @(
        (Join-Path $projectRoot 'workspace'),
        (Join-Path $projectRoot 'temp')
    )
    $protectedPaths = @(
        $projectRoot,
        (Join-Path $projectRoot 'workspace'),
        (Join-Path $projectRoot 'temp'),
        (Join-Path $projectRoot 'skill'),
        (Join-Path $projectRoot 'tools')
    ) | ForEach-Object { [System.IO.Path]::GetFullPath($_).TrimEnd('\') }

    if (-not ($allowedRoots | Where-Object { Test-IsWithinPath -Path $fullPath -Root $_ })) {
        throw "OutputDir must be a project subdirectory under D:\reverse_ENV\workspace\ or D:\reverse_ENV\temp\: $fullPath"
    }

    if ($protectedPaths -contains $fullPath) {
        throw "Refusing to use a protected directory as OutputDir: $fullPath"
    }

    if (Test-IsWithinPath -Path $ResolvedInput -Root $fullPath) {
        throw "OutputDir cannot contain the input artifact: $fullPath"
    }

    return $fullPath
}

function Expand-ZipSafely {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $destinationRoot = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $archive.Entries) {
            $relative = $entry.FullName.Replace('/', '\')
            if ([string]::IsNullOrWhiteSpace($relative)) {
                continue
            }

            $target = [System.IO.Path]::GetFullPath((Join-Path $destinationRoot $relative))
            if (-not (Test-IsWithinPath -Path $target -Root $destinationRoot)) {
                throw "Unsafe archive entry escapes the extraction directory: $($entry.FullName)"
            }

            if ([string]::IsNullOrEmpty($entry.Name)) {
                New-Item -ItemType Directory -Path $target -Force | Out-Null
                continue
            }

            $parent = Split-Path -Parent $target
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
        }
    }
    finally {
        $archive.Dispose()
    }
}

foreach ($tool in @($javaPath, $vineflowerPath)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required project-local tool not found: $tool"
    }
}

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).ProviderPath
if (-not (Test-Path -LiteralPath $resolvedInput -PathType Leaf)) {
    throw "InputPath is not a file: $resolvedInput"
}

$extension = [System.IO.Path]::GetExtension($resolvedInput).ToLowerInvariant()
if ($extension -notin @('.apk', '.dex', '.jar', '.aar', '.class')) {
    throw "Unsupported input type '$extension'. Expected APK, DEX, JAR, AAR, or CLASS."
}

$baseName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedInput)
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path (Split-Path -Parent $resolvedInput) ($baseName + '-vineflower')
}
$resolvedOutput = Assert-SafeOutputPath -Path $OutputDir -ResolvedInput $resolvedInput

if (Test-Path -LiteralPath $resolvedOutput) {
    $outputItem = Get-Item -LiteralPath $resolvedOutput -Force
    if (($outputItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to clean or reuse a reparse-point OutputDir: $resolvedOutput"
    }

    if ($Clean) {
        Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
    }
    elseif ((Get-ChildItem -LiteralPath $resolvedOutput -Force | Select-Object -First 1)) {
        throw "OutputDir is not empty; pass -Clean or choose another directory: $resolvedOutput"
    }
}

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$sourcesDir = Join-Path $resolvedOutput 'sources'
$intermediateDir = Join-Path $resolvedOutput '.intermediate'
$summaryPath = Join-Path $resolvedOutput 'vineflower-summary.json'
New-Item -ItemType Directory -Path $sourcesDir -Force | Out-Null
New-Item -ItemType Directory -Path $intermediateDir -Force | Out-Null

$sourceArtifacts = @()
$metadataArtifacts = @()
$dex2JarExitCode = $null
$vineflowerExitCode = $null
$failureMessage = $null

try {
    switch ($extension) {
        '.jar' {
            $sourceArtifacts = @($resolvedInput)
        }
        '.class' {
            $sourceArtifacts = @($resolvedInput)
        }
        '.aar' {
            $aarRoot = Join-Path $intermediateDir 'aar'
            Expand-ZipSafely -ArchivePath $resolvedInput -Destination $aarRoot

            $primaryJar = Join-Path $aarRoot 'classes.jar'
            if (Test-Path -LiteralPath $primaryJar -PathType Leaf) {
                $sourceArtifacts += $primaryJar
            }

            $libsDir = Join-Path $aarRoot 'libs'
            if (Test-Path -LiteralPath $libsDir -PathType Container) {
                $sourceArtifacts += @(
                    Get-ChildItem -LiteralPath $libsDir -Filter '*.jar' -File -Recurse |
                        Sort-Object FullName |
                        ForEach-Object { $_.FullName }
                )
            }

            if ($sourceArtifacts.Count -eq 0) {
                throw 'AAR contains neither classes.jar nor libs/*.jar.'
            }

            $aarMetadataDir = Join-Path $resolvedOutput 'aar-metadata'
            foreach ($name in @('AndroidManifest.xml', 'R.txt', 'proguard.txt', 'consumer-rules.pro')) {
                $candidate = Join-Path $aarRoot $name
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    New-Item -ItemType Directory -Path $aarMetadataDir -Force | Out-Null
                    $destination = Join-Path $aarMetadataDir $name
                    Copy-Item -LiteralPath $candidate -Destination $destination
                    $metadataArtifacts += $destination
                }
            }
        }
        default {
            if (-not (Test-Path -LiteralPath $dex2JarPath -PathType Leaf)) {
                throw "dex2jar is required for $extension input but was not found: $dex2JarPath"
            }

            $convertedJar = Join-Path $intermediateDir ($baseName + '-dex2jar.jar')
            $oldJavaHome = $env:JAVA_HOME
            $oldPath = $env:PATH
            try {
                $env:JAVA_HOME = Join-Path $projectRoot 'tools\jdk'
                $env:PATH = (Join-Path $projectRoot 'tools\jdk\bin') + ';' + $oldPath
                & $dex2JarPath -f -o $convertedJar $resolvedInput
                $dex2JarExitCode = $LASTEXITCODE
            }
            finally {
                $env:JAVA_HOME = $oldJavaHome
                $env:PATH = $oldPath
            }

            if (-not (Test-Path -LiteralPath $convertedJar -PathType Leaf)) {
                throw "dex2jar did not produce an output JAR (exit $dex2JarExitCode)."
            }
            $sourceArtifacts = @($convertedJar)
        }
    }

    $vineflowerArgs = @(
        '-jar',
        $vineflowerPath,
        '--folder',
        '--log-level=warn',
        '--skip-extra-files=true'
    )
    if ($RenameMembers) {
        $vineflowerArgs += '--rename-members=true'
    }
    $vineflowerArgs += $sourceArtifacts
    $vineflowerArgs += $sourcesDir

    & $javaPath @vineflowerArgs
    $vineflowerExitCode = $LASTEXITCODE
}
catch {
    $failureMessage = $_.Exception.Message
}

$javaCount = (Get-ChildItem -LiteralPath $sourcesDir -Filter '*.java' -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
$kotlinCount = (Get-ChildItem -LiteralPath $sourcesDir -Filter '*.kt' -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
$sourceCount = $javaCount + $kotlinCount
$status = if ($failureMessage) {
    'failed'
}
elseif ($sourceCount -gt 0 -and $vineflowerExitCode -eq 0) {
    'success'
}
elseif ($sourceCount -gt 0) {
    'partial'
}
else {
    'failed'
}

if (-not $KeepIntermediate -and (Test-Path -LiteralPath $intermediateDir -PathType Container)) {
    Remove-Item -LiteralPath $intermediateDir -Recurse -Force
}

$summary = [ordered]@{
    schema_version = 1
    input = $resolvedInput
    input_type = $extension.TrimStart('.')
    input_sha256 = (Get-FileHash -LiteralPath $resolvedInput -Algorithm SHA256).Hash
    output = $resolvedOutput
    status = $status
    options = [ordered]@{
        rename_members = [bool]$RenameMembers
        keep_intermediate = [bool]$KeepIntermediate
    }
    tools = [ordered]@{
        java = $javaPath
        vineflower = $vineflowerPath
        dex2jar = if ($extension -in @('.apk', '.dex')) { $dex2JarPath } else { $null }
    }
    stages = [ordered]@{
        dex2jar_exit_code = $dex2JarExitCode
        vineflower_exit_code = $vineflowerExitCode
    }
    artifacts = [ordered]@{
        sources = $sourcesDir
        java_files = $javaCount
        kotlin_files = $kotlinCount
        metadata = $metadataArtifacts
        intermediate_sources = if ($KeepIntermediate) { $sourceArtifacts } else { @() }
    }
    limitation = if ($extension -in @('.apk', '.dex')) {
        'dex2jar/Vineflower is a comparison path only; jadx/apktool remain authoritative for Android resources, smali, runtime names, and rebuild work.'
    }
    elseif ($extension -eq '.aar') {
        'Only classes.jar and libs/*.jar are decompiled; Android resources remain metadata, not Java/Kotlin source.'
    }
    else {
        'Decompiler output is evidence for review, not proof of exact source reconstruction.'
    }
    error = $failureMessage
}

$summaryJson = ($summary | ConvertTo-Json -Depth 8) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText(
    $summaryPath,
    $summaryJson + "`n",
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "status=$status"
Write-Output "sources=$sourcesDir"
Write-Output "java_files=$javaCount"
Write-Output "kotlin_files=$kotlinCount"
Write-Output "summary=$summaryPath"

if ($status -eq 'failed') {
    if ($failureMessage) {
        throw $failureMessage
    }
    throw 'Vineflower produced no Java or Kotlin source files; inspect vineflower-summary.json.'
}

if ($status -eq 'partial') {
    Write-Warning "Vineflower returned exit code $vineflowerExitCode but produced source files; inspect the output before use."
}
