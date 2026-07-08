param(
  [string]$Root = "D:\reverse_ENV",
  [string]$XbsRoot = "D:\reverse_ENV\storage\xbsReverseSkill\web-js-env-patcher",
  [string]$NodePath = "D:\reverse_ENV\tools\node\node.exe",
  [string]$PythonPath = "D:\reverse_ENV\.venv\Scripts\python.exe",
  [switch]$Json
)

$ErrorActionPreference = "Stop"

function Test-File($Path) {
  return [System.IO.File]::Exists($Path)
}

function Test-Dir($Path) {
  return [System.IO.Directory]::Exists($Path)
}

function Quote-Arg([string]$Arg) {
  if ($null -eq $Arg) { return '""' }
  if ($Arg -notmatch '[\s"]') { return $Arg }
  return '"' + ($Arg -replace '\', '\' -replace '"', '\"') + '"'
}

function Invoke-Capture($FilePath, [string[]]$Arguments, $WorkingDirectory) {
  if (!(Test-File $FilePath)) {
    return @{ ok = $false; exitCode = $null; stdout = ""; stderr = "missing executable: $FilePath" }
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = (($Arguments | ForEach-Object { Quote-Arg $_ }) -join ' ')
  $psi.WorkingDirectory = $WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $p = [System.Diagnostics.Process]::Start($psi)
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  return @{ ok = ($p.ExitCode -eq 0); exitCode = $p.ExitCode; stdout = $stdout.Trim(); stderr = $stderr.Trim() }
}

$rootFull = [System.IO.Path]::GetFullPath($Root)
$xbsFull = [System.IO.Path]::GetFullPath($XbsRoot)
$nodeFull = [System.IO.Path]::GetFullPath($NodePath)
$pythonFull = [System.IO.Path]::GetFullPath($PythonPath)
$ruyiTraceHome = [System.IO.Path]::Combine($rootFull, "tools", "ruyitrace")

$nodeVersion = Invoke-Capture $nodeFull @("--version") $rootFull
$nodeAbi = Invoke-Capture $nodeFull @("-p", "process.versions.modules") $rootFull
$pythonVersion = Invoke-Capture $pythonFull @("--version") $rootFull

$addonCheck = $null
$ivmCheck = $null
if (Test-Dir $xbsFull) {
  $addonScript = [System.IO.Path]::Combine($xbsFull, "scripts", "load_native_addon.js")
  $ivmScript = [System.IO.Path]::Combine($xbsFull, "scripts", "check_xbs_isolated_vm.js")
  if (Test-File $addonScript) { $addonCheck = Invoke-Capture $nodeFull @($addonScript, "--json") $xbsFull }
  if (Test-File $ivmScript) { $ivmCheck = Invoke-Capture $nodeFull @($ivmScript, "--json") $xbsFull }
}

$result = [ordered]@{
  root = $rootFull
  xbsRoot = $xbsFull
  xbsRootExists = (Test-Dir $xbsFull)
  mainNode = [ordered]@{
    path = $nodeFull
    exists = (Test-File $nodeFull)
    version = $nodeVersion.stdout
    abi = $nodeAbi.stdout
    role = "project-main-node-for-mcp-do-not-replace"
  }
  python = [ordered]@{
    path = $pythonFull
    exists = (Test-File $pythonFull)
    version = $pythonVersion.stdout
  }
  ruyiTrace = [ordered]@{
    home = $ruyiTraceHome
    exists = (Test-Dir $ruyiTraceHome)
    ps1 = [System.IO.Path]::Combine($ruyiTraceHome, "ruyitrace.ps1")
    ps1Exists = (Test-File ([System.IO.Path]::Combine($ruyiTraceHome, "ruyitrace.ps1")))
    analyzer = [System.IO.Path]::Combine($ruyiTraceHome, "trace_analyzer.py")
    analyzerExists = (Test-File ([System.IO.Path]::Combine($ruyiTraceHome, "trace_analyzer.py")))
  }
  isolation = [ordered]@{
    runtimeRoot = [System.IO.Path]::Combine($rootFull, "tools", "web-env", "runtimes")
    rule = "Do not replace tools\\node\\node.exe. Put Node25/Node26/addon/isolated-vm/TLS clients under tools\\web-env\\runtimes or workspace\\<project>\\.runtime."
    autoInstall = $false
  }
  xbsChecks = [ordered]@{
    addon = $addonCheck
    isolatedVm = $ivmCheck
  }
}

if ($Json) {
  $result | ConvertTo-Json -Depth 8
  exit 0
}

Write-Output "# web-env isolation check"
Write-Output ""
Write-Output "- Root: $($result.root)"
Write-Output "- xbsRoot: $($result.xbsRoot)"
Write-Output "- xbsRootExists: $($result.xbsRootExists)"
Write-Output "- Main Node: $($result.mainNode.path)"
Write-Output "- Main Node version: $($result.mainNode.version)"
Write-Output "- Main Node ABI: $($result.mainNode.abi)"
Write-Output "- Python: $($result.python.path) ($($result.python.version))"
Write-Output "- RuyiTrace home: $($result.ruyiTrace.home)"
Write-Output "- RuyiTrace exists: $($result.ruyiTrace.exists)"
Write-Output ""
Write-Output "## Isolation rules"
Write-Output ""
Write-Output "- Do not replace or switch D:\reverse_ENV\tools\node\node.exe."
Write-Output "- Put Node25/Node26/addon/xbs-isolated-vm/TLS clients under $($result.isolation.runtimeRoot) or case .runtime."
Write-Output "- This script does not install dependencies, write PATH, or write user-level environment variables."
Write-Output ""
Write-Output "## xbs native check summary"
Write-Output ""
if ($addonCheck) {
  Write-Output "### addon.node"
  Write-Output ""
  Write-Output '```json'
  Write-Output $addonCheck.stdout
  Write-Output '```'
} else {
  Write-Output "- addon.node: not checked; xbsRoot or script missing."
}
Write-Output ""
if ($ivmCheck) {
  Write-Output "### xbs isolated-vm"
  Write-Output ""
  Write-Output '```json'
  Write-Output $ivmCheck.stdout
  Write-Output '```'
} else {
  Write-Output "- xbs isolated-vm: not checked; xbsRoot or script missing."
}
