param(
    [ValidateSet('setup', 'build', 'serve', 'test', 'package', 'release')]
    [string]$Action = 'serve',
    [int]$Port = 8765,
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Befehl fehlgeschlagen: $Executable (Exit $LASTEXITCODE)" }
}
if ($Action -eq 'setup') {
    if (-not (Test-Path -LiteralPath $pythonPath)) { Invoke-Checked 'python' @('-m', 'venv', '.venv') }
    Invoke-Checked $pythonPath @('-m', 'pip', 'install', '-e', '.[pipeline,dev]')
    Invoke-Checked 'npm.cmd' @('ci', '--prefix', 'interactive', '--ignore-scripts')
    return
}
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Bitte zuerst .\dev.ps1 setup ausführen.' }
if ($Action -eq 'test') {
    Invoke-Checked $pythonPath @('-m', 'pytest')
    Invoke-Checked 'npm.cmd' @('test', '--prefix', 'interactive')
    if (Test-Path -LiteralPath 'course.yaml') { Invoke-Checked $pythonPath @('-m', 'pipeline', 'offline') }
    return
}
if (-not (Test-Path -LiteralPath 'course.yaml')) { throw 'Diesen Befehl im erzeugten Kursrepo ausführen; zuerst pipeline new verwenden.' }
Invoke-Checked $pythonPath @('-m', 'pipeline', 'audio-reader')
if ($Action -in @('package', 'release')) { Invoke-Checked $pythonPath @('-m', 'pipeline', 'package-reader') }
if ($Action -eq 'release') {
    foreach ($command in @('export', 'export-notebooklm', 'release')) { Invoke-Checked $pythonPath @('-m', 'pipeline', $command) }
}
if ($Action -eq 'serve') {
    $serveArgs = @('-m', 'pipeline', 'serve', '--port', [string]$Port)
    if (-not $NoOpen) { $serveArgs += '--open' }
    Invoke-Checked $pythonPath $serveArgs
}
