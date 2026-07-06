<#
.SYNOPSIS
Runs a lightweight radare2 recon pass and writes raw evidence under D:\reverse_ENV\workspace.

.PARAMETER TargetPath
Binary file to inspect.

.PARAMETER ProjectName
Workspace project directory name. Output goes to D:\reverse_ENV\workspace\<ProjectName>\radare2-recon.

.PARAMETER OutputDir
Explicit output directory under D:\reverse_ENV\workspace.

.PARAMETER RunAnalysis
Also runs portable radare2.exe with -A for a compact analysis pass.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [int]$StringsLimit = 40,

    [int]$ImportsLimit = 80,

    [switch]$RunAnalysis,

    [string]$ProjectName,

    [string]$OutputDir
)

[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = New-Object System.Text.UTF8Encoding $false

$ErrorActionPreference = 'Stop'

$RepoRoot = 'D:\reverse_ENV'
$WorkspaceRoot = Join-Path $RepoRoot 'workspace'
$Radare2Bin = Join-Path $RepoRoot 'tools\radare2\bin'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Get-PortableTool {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FileName
    )

    $toolPath = Join-Path $Radare2Bin $FileName
    if (Test-Path -LiteralPath $toolPath -PathType Leaf) {
        return $toolPath
    }

    throw "Missing required tool: $toolPath"
}

function Get-SafeName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $safe = $Name -replace '[\\/:*?"<>|]', '_'
    $safe = $safe.Trim()
    if ([string]::IsNullOrWhiteSpace($safe)) {
        throw 'ProjectName resolved to an empty directory name.'
    }
    return $safe
}

function Resolve-ReconOutputDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,

        [string]$Project,

        [string]$RequestedOutputDir
    )

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

    if (-not [string]::IsNullOrWhiteSpace($RequestedOutputDir)) {
        $fullOutputDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RequestedOutputDir)
        $workspaceFull = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WorkspaceRoot)
        $workspacePrefix = $workspaceFull.TrimEnd('\') + '\'
        if (($fullOutputDir -ne $workspaceFull) -and (-not $fullOutputDir.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase))) {
            throw "OutputDir must be under workspace: $workspaceFull"
        }
        New-Item -ItemType Directory -Force -Path $fullOutputDir | Out-Null
        return $fullOutputDir
    }

    if ([string]::IsNullOrWhiteSpace($Project)) {
        $Project = [System.IO.Path]::GetFileNameWithoutExtension($Target)
    }

    $safeProject = Get-SafeName -Name $Project
    $targetName = Get-SafeName -Name ([System.IO.Path]::GetFileNameWithoutExtension($Target))
    $fullOutputDir = Join-Path (Join-Path $WorkspaceRoot $safeProject) (Join-Path 'radare2-recon' "$targetName-$timestamp")
    New-Item -ItemType Directory -Force -Path $fullOutputDir | Out-Null
    return $fullOutputDir
}

function Write-Utf8NoBomLines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [AllowEmptyCollection()]
        [string[]]$Lines
    )

    $text = ''
    if ($null -ne $Lines -and $Lines.Count -gt 0) {
        $text = [string]::Join("`n", $Lines) + "`n"
    }
    [System.IO.File]::WriteAllText($Path, $text, $Utf8NoBom)
}

function Write-Utf8NoBomText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [AllowEmptyString()]
        [string]$Text
    )

    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$ExePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$RawPath
    )

    $lines = @(& $ExePath @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    $exitCode = $LASTEXITCODE
    Write-Utf8NoBomLines -Path $RawPath -Lines $lines

    return [pscustomobject]@{
        name = $Name
        exe = $ExePath
        arguments = $Arguments
        rawPath = $RawPath
        exitCode = $exitCode
        totalLines = $lines.Count
        lines = $lines
    }
}

function Write-ConsoleSection {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title
    )

    Write-Output ''
    Write-Output "=== $Title ==="
}

function Write-Summary {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Result,

        [int]$Limit = 20
    )

    $shown = [Math]::Min($Limit, $Result.totalLines)
    $truncated = $Result.totalLines -gt $shown

    Write-ConsoleSection -Title $Result.name
    Write-Output ("raw: {0}" -f $Result.rawPath)
    Write-Output ("exitCode: {0}; lines: {1}; shown: {2}; truncated: {3}" -f $Result.exitCode, $Result.totalLines, $shown, $truncated)

    if ($shown -gt 0) {
        for ($index = 0; $index -lt $shown; $index++) {
            Write-Output $Result.lines[$index]
        }
    }
}

function New-Report {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,

        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,

        [Parameter(Mandatory = $true)]
        [object[]]$Results
    )

    $report = New-Object System.Collections.Generic.List[string]
    $report.Add('# radare2 recon report')
    $report.Add('')
    $report.Add(('- target: `{0}`' -f $Target))
    $report.Add(('- outputDir: `{0}`' -f $OutputDirectory))
    $report.Add(('- generatedAt: `{0}`' -f (Get-Date -Format o)))
    $report.Add('')
    $report.Add('## Evidence')

    foreach ($result in $Results) {
        $report.Add('')
        $report.Add(("### {0}" -f $result.name))
        $report.Add(('- raw: `{0}`' -f $result.rawPath))
        $report.Add(('- exitCode: `{0}`' -f $result.exitCode))
        $report.Add(('- totalLines: `{0}`' -f $result.totalLines))
    }

    Write-Utf8NoBomLines -Path (Join-Path $OutputDirectory 'report.md') -Lines $report.ToArray()
}

function New-Triage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,

        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,

        [Parameter(Mandatory = $true)]
        [object[]]$Results
    )

    $triage = New-Object System.Collections.Generic.List[string]
    $failed = @($Results | Where-Object { $_.exitCode -ne 0 })
    $triage.Add('# radare2 recon triage')
    $triage.Add('')
    $triage.Add(('- target: `{0}`' -f $Target))
    $triage.Add(('- evidenceDir: `{0}`' -f $OutputDirectory))
    $triage.Add(('- failedCommands: `{0}`' -f $failed.Count))
    $triage.Add('')
    $triage.Add('## Notes')
    $triage.Add('')
    $triage.Add('- Console output is a summary only.')
    $triage.Add('- Raw command output is the primary evidence.')
    $triage.Add('- Truncated summaries list shown line count and total line count.')

    Write-Utf8NoBomLines -Path (Join-Path $OutputDirectory 'triage.md') -Lines $triage.ToArray()
}

function New-FindingsJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,

        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,

        [Parameter(Mandatory = $true)]
        [object[]]$Results
    )

    $items = @()
    foreach ($result in $Results) {
        $items += [pscustomobject]@{
            name = $result.name
            exe = $result.exe
            arguments = $result.arguments
            rawPath = $result.rawPath
            exitCode = $result.exitCode
            totalLines = $result.totalLines
        }
    }

    $jsonObject = [pscustomobject]@{
        target = $Target
        outputDir = $OutputDirectory
        generatedAt = (Get-Date -Format o)
        evidence = $items
    }

    $json = $jsonObject | ConvertTo-Json -Depth 6
    Write-Utf8NoBomText -Path (Join-Path $OutputDirectory 'findings.json') -Text ($json + "`n")
}

$rabin2Path = Get-PortableTool -FileName 'rabin2.exe'
$radare2Path = if ($RunAnalysis) { Get-PortableTool -FileName 'radare2.exe' } else { $null }

$resolvedPath = Resolve-Path -LiteralPath $TargetPath
$target = $resolvedPath.Path
$outDir = Resolve-ReconOutputDir -Target $target -Project $ProjectName -RequestedOutputDir $OutputDir

$results = New-Object System.Collections.Generic.List[object]

Write-Output ("target: {0}" -f $target)
Write-Output ("outputDir: {0}" -f $outDir)

$results.Add((Invoke-NativeCapture -Name 'basic-info' -ExePath $rabin2Path -Arguments @('-I', '--', $target) -RawPath (Join-Path $outDir 'raw_basic_info.txt')))
$results.Add((Invoke-NativeCapture -Name 'sections' -ExePath $rabin2Path -Arguments @('-S', '--', $target) -RawPath (Join-Path $outDir 'raw_sections.txt')))
$results.Add((Invoke-NativeCapture -Name 'imports' -ExePath $rabin2Path -Arguments @('-i', '--', $target) -RawPath (Join-Path $outDir 'raw_imports.txt')))
$results.Add((Invoke-NativeCapture -Name 'exports' -ExePath $rabin2Path -Arguments @('-E', '--', $target) -RawPath (Join-Path $outDir 'raw_exports.txt')))
$results.Add((Invoke-NativeCapture -Name 'strings' -ExePath $rabin2Path -Arguments @('-zz', '--', $target) -RawPath (Join-Path $outDir 'raw_strings.txt')))

if ($RunAnalysis) {
    $results.Add((Invoke-NativeCapture -Name 'analysis' -ExePath $radare2Path -Arguments @('-A', '-q', '-c', 's entry0;afl;iz;ii;q', '--', $target) -RawPath (Join-Path $outDir 'raw_analysis.txt')))
}

foreach ($result in $results) {
    $limit = 20
    if ($result.name -eq 'imports') {
        $limit = $ImportsLimit
    }
    elseif ($result.name -eq 'strings') {
        $limit = $StringsLimit
    }

    Write-Summary -Result $result -Limit $limit
}

New-Report -Target $target -OutputDirectory $outDir -Results $results.ToArray()
New-Triage -Target $target -OutputDirectory $outDir -Results $results.ToArray()
New-FindingsJson -Target $target -OutputDirectory $outDir -Results $results.ToArray()

Write-ConsoleSection -Title 'artifacts'
Write-Output ("report: {0}" -f (Join-Path $outDir 'report.md'))
Write-Output ("triage: {0}" -f (Join-Path $outDir 'triage.md'))
Write-Output ("findings: {0}" -f (Join-Path $outDir 'findings.json'))
