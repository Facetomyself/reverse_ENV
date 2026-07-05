<#
.SYNOPSIS
  Launch js-reverse-mcp with Chrome.

  TWO MODES:

  1. DEFAULT (--browserUrl): Start user's system Chrome with remote debugging
     port, wait for CDP, then connect js-reverse-mcp via --browserUrl.
     Patchright protocol-level stealth only — suitable for most sites.

  2. CLOAK (-Cloak): Run js-reverse-mcp with --cloak — CloakBrowser stealth
     Chromium with 57 source-level fingerprint patches (canvas/WebGL/audio/GPU).
     Use for STRONG anti-detection sites (e.g. 51job, zhihu, Cloudflare-protected).
     Auto-downloads ~200MB binary on first run, cached thereafter.

  For MCP stdio transport — forwards stdin/stdout between MCP client
  and the js-reverse-mcp node process.
#>

param(
    [switch]$Cloak,

    # --browserUrl mode params
    [int]$Port = 9222,
    [string]$SystemChrome = "C:\Program Files\Google\Chrome\Application\chrome.exe",
    [string]$BundledChromium = "D:\reverse_ENV\tools\chromium\chrome-win\chrome.exe",
    [string]$ProfileDir = "D:\reverse_ENV\tools\chromium\profile",

    # Shared
    [string]$NodeExe = "D:\reverse_ENV\tools\node\node.exe",
    [string]$JsReverseMcp = "D:\reverse_ENV\mcp\js-reverse-mcp\node_modules\js-reverse-mcp\build\src\index.js"
)

$ErrorActionPreference = "Stop"

# =========================================================================
# CLOAK MODE: CloakBrowser stealth Chromium
# =========================================================================
if ($Cloak) {
    [Console]::Error.WriteLine("[start-js-reverse] CLOAK mode — CloakBrowser stealth Chromium (57 fingerprint patches)")

    $psiNode = New-Object System.Diagnostics.ProcessStartInfo
    $psiNode.FileName = $NodeExe
    $psiNode.Arguments = "`"$JsReverseMcp`" --cloak"
    $psiNode.UseShellExecute = $false
    $psiNode.RedirectStandardInput = $true
    $psiNode.RedirectStandardOutput = $true
    $psiNode.RedirectStandardError = $true

    $nodeProc = [System.Diagnostics.Process]::Start($psiNode)

    # Forward stdin -> nodeProc
    $stdinTask = [System.Threading.Tasks.Task]::Run({
        param($proc)
        try {
            $buf = New-Object byte[] 8192
            while ($true) {
                $n = [System.Console]::OpenStandardInput().Read($buf, 0, $buf.Length)
                if ($n -le 0) { break }
                $proc.StandardInput.BaseStream.Write($buf, 0, $n)
                $proc.StandardInput.BaseStream.Flush()
            }
        } catch {}
        finally {
            try { $proc.StandardInput.Close() } catch {}
        }
    }, $nodeProc)

    # Forward nodeProc stdout -> stdout
    $stdoutTask = [System.Threading.Tasks.Task]::Run({
        param($proc)
        try {
            $buf = New-Object byte[] 8192
            while ($true) {
                $n = $proc.StandardOutput.BaseStream.Read($buf, 0, $buf.Length)
                if ($n -le 0) { break }
                [System.Console]::OpenStandardOutput().Write($buf, 0, $n)
            }
        } catch {}
    }, $nodeProc)

    # Forward nodeProc stderr -> stderr
    $stderrTask = [System.Threading.Tasks.Task]::Run({
        param($proc)
        try {
            $buf = New-Object byte[] 8192
            while ($true) {
                $n = $proc.StandardError.BaseStream.Read($buf, 0, $buf.Length)
                if ($n -le 0) { break }
                [System.Console]::OpenStandardError().Write($buf, 0, $n)
            }
        } catch {}
    }, $nodeProc)

    $nodeProc.WaitForExit()
    [System.Threading.Tasks.Task]::WaitAll(@($stdinTask, $stdoutTask, $stderrTask), 3000)
    exit $nodeProc.ExitCode
}

# =========================================================================
# DEFAULT MODE: System Chrome + --browserUrl
# =========================================================================

# -- Pick Chrome binary --------------------------------------------------
if (Test-Path $SystemChrome) {
    $ChromeExe = $SystemChrome
    [Console]::Error.WriteLine("[start-js-reverse] Using system Chrome: $ChromeExe")
} elseif (Test-Path $BundledChromium) {
    $ChromeExe = $BundledChromium
    [Console]::Error.WriteLine("[start-js-reverse] System Chrome not found, using bundled Chromium: $ChromeExe")
} else {
    [Console]::Error.WriteLine("[start-js-reverse] FATAL: No Chrome/Chromium found")
    exit 1
}

# 1. Kill any Chrome already on our debug port ---------------------------
$existing = Get-Process -Name "chrome" -ErrorAction SilentlyContinue |
    Where-Object {
        try {
            (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match "--remote-debugging-port=$Port"
        } catch { $false }
    }
if ($existing) {
    [Console]::Error.WriteLine("[start-js-reverse] Stopping existing debug Chrome (port $Port)...")
    $existing | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 2. Start Chrome with debug port ----------------------------------------
[Console]::Error.WriteLine("[start-js-reverse] Starting Chrome on port $Port...")

$chromeArgs = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-translate",
    "--disable-extensions",
    "--hide-scrollbars",
    "--mute-audio"
)

$psiChrome = New-Object System.Diagnostics.ProcessStartInfo
$psiChrome.FileName = $ChromeExe
$psiChrome.Arguments = $chromeArgs -join " "
$psiChrome.UseShellExecute = $false
$psiChrome.RedirectStandardOutput = $true
$psiChrome.RedirectStandardError = $true

$chromiumProc = [System.Diagnostics.Process]::Start($psiChrome)

# 3. Wait for CDP endpoint -----------------------------------------------
[Console]::Error.WriteLine("[start-js-reverse] Waiting for CDP on port $Port...")
$maxWait = 30
for ($i = 0; $i -lt $maxWait; $i++) {
    try {
        $req = [System.Net.WebRequest]::Create("http://127.0.0.1:$Port/json/version")
        $req.Timeout = 2000
        $resp = $req.GetResponse()
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $body = $reader.ReadToEnd()
        $json = $body | ConvertFrom-Json
        [Console]::Error.WriteLine("[start-js-reverse] CDP ready: $($json.Browser)")
        $reader.Close()
        $resp.Close()
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($i -ge $maxWait) {
    [Console]::Error.WriteLine("[start-js-reverse] CDP timeout after ${maxWait}s")
    if (-not $chromiumProc.HasExited) { $chromiumProc.Kill() }
    exit 2
}

# 4. Cleanup handler -----------------------------------------------------
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    [Console]::Error.WriteLine("[start-js-reverse] Shutting down Chrome...")
    try { Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Stop-Process -Force } catch {}
}

# 5. Exec js-reverse-mcp (stdio forwarding for MCP) ----------------------
[Console]::Error.WriteLine("[start-js-reverse] Starting js-reverse-mcp (--browserUrl mode, stdio forwarding)...")

$psiNode = New-Object System.Diagnostics.ProcessStartInfo
$psiNode.FileName = $NodeExe
$psiNode.Arguments = "`"$JsReverseMcp`" --browserUrl http://127.0.0.1:$Port"
$psiNode.UseShellExecute = $false
$psiNode.RedirectStandardInput = $true
$psiNode.RedirectStandardOutput = $true
$psiNode.RedirectStandardError = $true

$nodeProc = [System.Diagnostics.Process]::Start($psiNode)

# Forward stdin -> nodeProc
$stdinTask = [System.Threading.Tasks.Task]::Run({
    param($proc)
    try {
        $buf = New-Object byte[] 8192
        while ($true) {
            $n = [System.Console]::OpenStandardInput().Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            $proc.StandardInput.BaseStream.Write($buf, 0, $n)
            $proc.StandardInput.BaseStream.Flush()
        }
    } catch {}
    finally {
        try { $proc.StandardInput.Close() } catch {}
    }
}, $nodeProc)

# Forward nodeProc stdout -> stdout
$stdoutTask = [System.Threading.Tasks.Task]::Run({
    param($proc)
    try {
        $buf = New-Object byte[] 8192
        while ($true) {
            $n = $proc.StandardOutput.BaseStream.Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            [System.Console]::OpenStandardOutput().Write($buf, 0, $n)
        }
    } catch {}
}, $nodeProc)

# Forward nodeProc stderr -> stderr
$stderrTask = [System.Threading.Tasks.Task]::Run({
    param($proc)
    try {
        $buf = New-Object byte[] 8192
        while ($true) {
            $n = $proc.StandardError.BaseStream.Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            [System.Console]::OpenStandardError().Write($buf, 0, $n)
        }
    } catch {}
}, $nodeProc)

$nodeProc.WaitForExit()

[System.Threading.Tasks.Task]::WaitAll(@($stdinTask, $stdoutTask, $stderrTask), 3000)

# Cleanup Chrome
[Console]::Error.WriteLine("[start-js-reverse] Node exited (code=$($nodeProc.ExitCode)), stopping Chrome...")
if (-not $chromiumProc.HasExited) {
    $chromiumProc.Kill()
}

exit $nodeProc.ExitCode
