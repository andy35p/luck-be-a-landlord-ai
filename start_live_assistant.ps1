param(
    [string]$PythonPath,
    [ValidateRange(1,60)][int]$Minutes = 5,
    [switch]$NoDisplay
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_live_python.ps1')
$PythonPath = Resolve-LivePython -PythonPath $PythonPath
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'package_manifest.json')) {
    & $PythonPath (Join-Path $PSScriptRoot 'verify_live_bundle.py') $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw 'Bundle integrity check failed. Re-extract a known build before starting.' }
}
$logDirectory = Join-Path $PSScriptRoot 'run-logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$log = Join-Path $logDirectory (('run-'+[guid]::NewGuid().ToString('N'))+'.jsonl')
Write-Host "Diagnostics: $log"
$options = @{PythonPath=$PythonPath; Seconds=($Minutes*60); MonitorGame=$true; EventLog=$log}
if (-not $NoDisplay) { $options.Display=$true }
& (Join-Path $PSScriptRoot 'watch_live_advice.ps1') @options
exit $LASTEXITCODE
