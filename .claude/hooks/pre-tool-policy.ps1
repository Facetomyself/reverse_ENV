$ErrorActionPreference = "Stop"

function Deny {
    param([string] $Reason)
    Write-Host "DENY: $Reason" -ForegroundColor Red
    exit 2
}

function Warn {
    param([string] $Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Add-Candidate {
    param(
        [System.Collections.Generic.List[string]] $Candidates,
        [string] $Name,
        [string] $Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    $likelyName = $Name -match '(^|_|\.)command$|(^|_|\.)cmd$|(^|_|\.)script$|shell_command|tool_input|input'
    $likelyValue = $Value -match 'git\s+|Remove-Item|rm\s+|del\s+|rmdir\s+|taskkill|Stop-Process|Start-Process|powershell|pwsh|cmd\.exe'

    if ($likelyName -or $likelyValue) {
        $Candidates.Add($Value)
    }
}

function Visit-Value {
    param(
        [object] $Value,
        [string] $Name,
        [System.Collections.Generic.List[string]] $Candidates
    )

    if ($null -eq $Value) {
        return
    }

    if ($Value -is [string]) {
        Add-Candidate -Candidates $Candidates -Name $Name -Value $Value
        return
    }

    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            Visit-Value -Value $Value[$key] -Name ([string] $key) -Candidates $Candidates
        }
        return
    }

    if ($Value -is [System.Collections.IEnumerable]) {
        foreach ($item in $Value) {
            Visit-Value -Value $item -Name $Name -Candidates $Candidates
        }
        return
    }

    foreach ($property in $Value.PSObject.Properties) {
        Visit-Value -Value $property.Value -Name $property.Name -Candidates $Candidates
    }
}

function Normalize-Command {
    param([string] $Command)
    return (($Command -replace "`r|`n", " ") -replace '\s+', ' ').Trim()
}

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payload)) {
    exit 0
}

$candidates = New-Object System.Collections.Generic.List[string]

try {
    $json = $payload | ConvertFrom-Json
    Visit-Value -Value $json -Name "" -Candidates $candidates
} catch {
    Add-Candidate -Candidates $candidates -Name "raw" -Value $payload
}

$commands = $candidates |
    ForEach-Object { Normalize-Command -Command $_ } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique

foreach ($command in $commands) {
    $lower = $command.ToLowerInvariant()

    if ($lower -match '\bgit\s+reset\s+--hard\b') {
        Deny "git reset --hard is blocked in reverse_ENV. Do not discard user or parallel terminal changes."
    }

    if ($lower -match '\bgit\s+checkout\s+--(?:\s|$)') {
        Deny "git checkout -- is blocked in reverse_ENV. Use an explicit non-destructive workflow."
    }

    if ($lower -match '\bgit\s+clean\s+-(?:[^\s]*f[^\s]*d|[^\s]*d[^\s]*f|xdf|fdx)\b') {
        Deny "git clean with force/delete flags is blocked in reverse_ENV."
    }

    if ($lower -match '\bgit\s+push\b' -and $lower -match '(\s|=)(--force|-f|--mirror|--delete)(\s|$)') {
        Deny "destructive git push mode is blocked. Use a normal push or ask explicitly before rewriting/deleting remote refs."
    }

    if ($lower -match '\b(remove-item|rm|del|erase|rmdir)\b' -and $lower -match 'd:\\reverse_env(?:[\\/])?(?:["''\s]|$)' -and $lower -match '(-recurse|-r\b|/s\b)') {
        Deny "recursive deletion of D:\reverse_ENV or its root is blocked."
    }

    if ($lower -match '\b(remove-item|rm|del|erase|rmdir)\b' -and $lower -match 'd:\\reverse_env[\\\/]\.git(?:[\\\/]|\b)') {
        Deny "deleting D:\reverse_ENV\.git or its contents is blocked."
    }

    if ($lower -match '\b(remove-item|rm|del|erase|rmdir)\b' -and $lower -match 'd:\\reverse_env[\\\/](workspace|storage)(?:[\\/])?(?:["''\s]|$)') {
        Deny "deleting protected reverse_ENV root paths (workspace, storage) is blocked."
    }

    if ($lower -match '\b(taskkill|stop-process)\b' -and $lower -match '(python|node|adb|java)' -and $lower -notmatch '(idalib_worker|ldplayer|dnplayer|frida|jadx)') {
        Warn "broad process termination detected. Keep it scoped to the intended tool/process tree."
    }

    if ($lower -match '\bgit\s+push\b') {
        Warn "git push detected. Confirm branch, remote, and unrelated working-tree changes before pushing."
    }
}

exit 0
