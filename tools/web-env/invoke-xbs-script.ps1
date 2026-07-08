param(
  [Parameter(Mandatory = $true)]
  [string]$Script,
  [string[]]$ScriptArgs = @(),
  [string]$Root = "D:\reverse_ENV",
  [string]$XbsRoot = "D:\reverse_ENV\storage\xbsReverseSkill\web-js-env-patcher",
  [string]$NodePath = "D:\reverse_ENV\tools\node\node.exe"
)

$ErrorActionPreference = "Stop"

$rootFull = [System.IO.Path]::GetFullPath($Root)
$xbsFull = [System.IO.Path]::GetFullPath($XbsRoot)
$nodeFull = [System.IO.Path]::GetFullPath($NodePath)
$scriptsDir = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($xbsFull, "scripts"))
if ([System.IO.Path]::GetFileName($Script) -ne $Script) {
  throw "Only script file names are allowed, not paths: $Script"
}
$scriptPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($scriptsDir, $Script))

if (!(Test-Path -LiteralPath $nodeFull -PathType Leaf)) {
  throw "Node not found: $nodeFull"
}
if (!(Test-Path -LiteralPath $scriptsDir -PathType Container)) {
  throw "xbs scripts directory not found: $scriptsDir. Clone into D:\reverse_ENV\storage\xbsReverseSkill or pass -XbsRoot."
}
$scriptsDirWithSep = $scriptsDir.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (!$scriptPath.StartsWith($scriptsDirWithSep, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Script path escapes xbs scripts directory: $scriptPath"
}
if (!(Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
  throw "xbs script not found: $scriptPath"
}
if ([System.IO.Path]::GetExtension($scriptPath) -ne ".js") {
  throw "Only .js checkers under xbs web-js-env-patcher scripts are allowed: $scriptPath"
}

$oldRuyiTraceHome = [Environment]::GetEnvironmentVariable("RUYI_TRACE_HOME", "Process")
$oldPath = [Environment]::GetEnvironmentVariable("PATH", "Process")
try {
  $nodeDir = [System.IO.Path]::GetDirectoryName($nodeFull)
  $venvScripts = [System.IO.Path]::Combine($rootFull, ".venv", "Scripts")
  $scopedPathParts = @($nodeDir, $venvScripts, $oldPath) | Where-Object { $_ -and ($_ -ne "") }
  [Environment]::SetEnvironmentVariable("PATH", ($scopedPathParts -join [System.IO.Path]::PathSeparator), "Process")
  $ruyiTraceHome = [System.IO.Path]::Combine($rootFull, "tools", "ruyitrace")
  if (Test-Path -LiteralPath $ruyiTraceHome -PathType Container) {
    [Environment]::SetEnvironmentVariable("RUYI_TRACE_HOME", $ruyiTraceHome, "Process")
  }

  Write-Host "[web-env] Node: $nodeFull"
  Write-Host "[web-env] xbsRoot: $xbsFull"
  Write-Host "[web-env] Script: $scriptPath"
  Write-Host "[web-env] RUYI_TRACE_HOME(process): $([Environment]::GetEnvironmentVariable('RUYI_TRACE_HOME', 'Process'))"
  Write-Host "[web-env] This wrapper does not install dependencies, switch main Node, or write system PATH."

  & $nodeFull $scriptPath @ScriptArgs
  exit $LASTEXITCODE
} finally {
  [Environment]::SetEnvironmentVariable("RUYI_TRACE_HOME", $oldRuyiTraceHome, "Process")
  [Environment]::SetEnvironmentVariable("PATH", $oldPath, "Process")
}
