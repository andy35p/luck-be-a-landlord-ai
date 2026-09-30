param(
    [string]$PythonPath,
    [int]$Seconds = 60,
    [switch]$Display,
    [string]$EventLog,
    [switch]$MonitorGame
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_live_python.ps1')
$PythonPath = Resolve-LivePython -PythonPath $PythonPath
$collectorDirectory = Join-Path $env:APPDATA 'Godot\app_userdata\Luck be a Landlord\landlordResearch'
if (-not (Test-Path -LiteralPath $collectorDirectory -PathType Container)) {
    throw 'Collector directory not found. Install the collector and start the game once before starting the assistant.'
}
$realNewest = Get-ChildItem -LiteralPath $collectorDirectory -Filter '*.jsonl' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name
$pythonNewest = & $PythonPath -c 'import pathlib,sys; p=list(pathlib.Path(sys.argv[1]).glob("*.jsonl")); print(max(p,key=lambda x:x.stat().st_mtime).name if p else "")' $collectorDirectory
if ($LASTEXITCODE -ne 0 -or $realNewest -ne $pythonNewest) {
    throw 'Python and Windows see different collector directories; use another Python runtime.'
}
$displayArgs = @()
if ($Display) { $displayArgs = @('--display-file', (Join-Path $collectorDirectory 'advice.json')) }
if ($EventLog) { $displayArgs += @('--event-log', $EventLog) }
if ($MonitorGame) {
    $games = @(Get-Process -Name 'Luck be a Landlord' -ErrorAction SilentlyContinue)
    if ($games.Count -ne 1) { throw 'Start exactly one game instance before using -MonitorGame.' }
    $displayArgs += @('--game-pid', $games[0].Id)
}
& $PythonPath (Join-Path $PSScriptRoot 'watch_live_advice.py') --directory $collectorDirectory --seconds $Seconds @displayArgs
exit $LASTEXITCODE
