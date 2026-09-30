param(
    [string]$GameDirectory = 'D:\SteamLibrary\steamapps\common\Luck be a Landlord',
    [string]$DataDirectory = "$env:APPDATA\Godot\app_userdata\Luck be a Landlord",
    [string]$PythonPath = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$BackupDirectory,
    [string]$ReportPath,
    [ValidateSet('0.5.0','0.7.0')][string]$CollectorVersion = '0.5.0'
)
# Read-only: never installs, launches the game, restores saves or clears history.
$ErrorActionPreference = 'Stop'
$checks = [System.Collections.Generic.List[object]]::new()
function Check($name, $passed, $detail) {
    $checks.Add([pscustomobject]@{name=$name;passed=[bool]$passed;detail=$detail})
}
$profileDirectory = if ($CollectorVersion -eq '0.7.0') { 'collector_v07' } else { 'collector_v05' }
$baseline = Get-Content -LiteralPath (Join-Path $PSScriptRoot "integrations/$profileDirectory/verified_build.json") -Raw | ConvertFrom-Json
$plugin = Join-Path $GameDirectory 'SlotWeave/mods/LandlordResearch'
Check 'game_executable' (Test-Path -LiteralPath (Join-Path $GameDirectory 'Luck be a Landlord.exe')) $GameDirectory
Check 'modloader' (Test-Path -LiteralPath (Join-Path $GameDirectory 'SlotWeave/version.json')) 'External SlotWeave installation; does not establish Workshop compatibility'
try {
    $manifest = Get-Content -LiteralPath (Join-Path $plugin 'manifest.json') -Raw | ConvertFrom-Json
    Check 'manifest' ($manifest.Id -eq 'LandlordResearch' -and $manifest.Metadata.Version -eq $baseline.version -and $manifest.AssemblyPath -eq 'LandlordResearch.dll') $manifest.Metadata.Version
} catch { Check 'manifest' $false $_.Exception.Message }
try {
    $hash = (Get-FileHash -LiteralPath (Join-Path $plugin 'LandlordResearch.dll') -Algorithm SHA256).Hash
    Check 'verified_production_binary' ($hash -eq $baseline.dll_sha256) $hash
} catch { Check 'verified_production_binary' $false $_.Exception.Message }
$feed = Join-Path $DataDirectory 'landlordResearch'
try {
    # Compare the entire visible inventory, not only the newest filename.
    $windowsFiles = @(Get-ChildItem -LiteralPath $feed -Filter '*.jsonl' -File | Sort-Object Name | ForEach-Object { "$($_.Name)|$($_.Length)" })
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Python runtime missing' }
    $pythonFiles = @(& $PythonPath -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); assert p.is_dir(); print("\n".join(f"{f.name}|{f.stat().st_size}" for f in sorted(p.glob("*.jsonl")) if f.is_file()))' $feed)
    if ($LASTEXITCODE -ne 0) { throw 'Python directory probe failed' }
    $pythonFiles = @($pythonFiles | Where-Object { $_ -ne '' })
    Check 'python_directory_visibility' (($windowsFiles -join "`n") -eq ($pythonFiles -join "`n")) "Windows=$($windowsFiles.Count), Python=$($pythonFiles.Count); run while game is closed to avoid concurrent writes"
} catch { Check 'python_directory_visibility' $false $_.Exception.Message }
if ($BackupDirectory) {
    foreach ($entry in @(
        @{folder='plugin-backup';target=$plugin;names=@('LandlordResearch.dll','manifest.json')},
        @{folder='save-backup';target=$DataDirectory;names=@('LBAL.save','LBAL-Settings.save','LBAL-Stats.save','LBAL-Stats.bak','LBAL-Sandbox-Data.save')}
    )) {
        foreach ($name in $entry.names) {
            try {
                $source = Join-Path (Join-Path $BackupDirectory $entry.folder) $name
                $target = Join-Path $entry.target $name
                $same = (Get-FileHash -LiteralPath $source).Hash -eq (Get-FileHash -LiteralPath $target).Hash
                Check "restored:$name" $same $target
            } catch { Check "restored:$name" $false $_.Exception.Message }
        }
    }
}
$result = [pscustomobject]@{
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    scope = 'Local installation and optional restoration only; no live freshness, gameplay or Workshop certification'
    passed = (@($checks | Where-Object { -not $_.passed }).Count -eq 0)
    checks = @($checks.ToArray())
}
$json = $result | ConvertTo-Json -Depth 5
if ($ReportPath) { $json | Set-Content -LiteralPath $ReportPath -Encoding utf8 }
$json
if (-not $result.passed) { exit 1 }
