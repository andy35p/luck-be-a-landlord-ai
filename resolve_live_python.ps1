function Resolve-LivePython {
    param([string]$PythonPath)
    # ASCII JSON keeps Unicode paths intact under Windows PowerShell and pwsh.
    $probe = 'import json,sys; print(json.dumps(sys.executable)) if sys.version_info >= (3,11) else sys.exit(1)'
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
            throw 'Python executable not found. Pass -PythonPath with its full path.'
        }
        $result = & $PythonPath -X utf8 -c $probe
        $resolved = if ($LASTEXITCODE -eq 0 -and $result) { $result | ConvertFrom-Json } else { $null }
        if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath "$resolved" -PathType Leaf)) {
            return "$resolved"
        }
        throw 'Python 3.11 or newer is required.'
    }
    foreach ($name in @('py', 'python')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        # Do not launch the Windows Store installation alias.
        if ($command.Source -like '*\Microsoft\WindowsApps\*') { continue }
        $arguments = @('-X', 'utf8', '-c', $probe)
        if ($name -eq 'py') { $arguments = @('-3') + $arguments }
        try {
            $result = & $command.Source @arguments 2>$null
            $resolved = if ($LASTEXITCODE -eq 0 -and $result) { $result | ConvertFrom-Json } else { $null }
            if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath "$resolved" -PathType Leaf)) {
                return "$resolved"
            }
        } catch { continue }
    }
    throw 'Python 3.11+ required. Install a regular Python runtime or pass -PythonPath with its full path.'
}
