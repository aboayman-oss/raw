$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSCommandPath
$python = Join-Path $root '.venv\Scripts\python.exe'
$iconPath = Join-Path $root 'assets\app_icon.ico'
$mainScript = Join-Path $root 'src\main.py'
$portableRelease = Join-Path $root 'release\portable'
$installerScript = Join-Path $root 'installer.iss'

if (-not (Test-Path $python)) {
    throw "Python virtual environment was not found at $python"
}

if (-not (Test-Path $iconPath)) {
    throw "App icon was not found at $iconPath"
}

function Get-InnoCompilerPath {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

$iscc = Get-InnoCompilerPath
if (-not $iscc) {
    Write-Host 'Installing Inno Setup via winget...'
    winget install --id JRSoftware.InnoSetup --silent --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
    $iscc = Get-InnoCompilerPath
}

if (-not $iscc) {
    throw 'Inno Setup compiler (ISCC.exe) is unavailable.'
}

Remove-Item (Join-Path $root 'build') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $root 'dist') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $root 'release') -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $portableRelease | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'release\installer') | Out-Null

$commonArgs = @(
    '--clean',
    '--noconfirm',
    '--windowed',
    '--icon', $iconPath,
    '--add-data', ((Join-Path $root 'assets') + ';assets'),
    '--add-data', ((Join-Path $root 'Data archive') + ';defaults'),
    '--hidden-import', 'openpyxl',
    '--collect-all', 'customtkinter'
)

Write-Host 'Building portable executable...'
& $python -m PyInstaller @commonArgs --onefile --name RFIDAttendanceManagerPortable $mainScript
Copy-Item (Join-Path $root 'dist\RFIDAttendanceManagerPortable.exe') $portableRelease

Write-Host 'Building installer payload...'
& $python -m PyInstaller @commonArgs --onedir --name RFIDAttendanceManager $mainScript

Write-Host 'Compiling installer...'
& $iscc $installerScript | Out-Host

Remove-Item (Join-Path $root 'build') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $root 'dist') -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'Build complete.'
Write-Host ('Portable:  ' + (Join-Path $root 'release\portable\RFIDAttendanceManagerPortable.exe'))
Write-Host ('Installer: ' + (Join-Path $root 'release\installer\RFIDAttendanceManagerSetup.exe'))