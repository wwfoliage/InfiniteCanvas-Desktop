param(
    [switch]$InstallDependencies,
    [switch]$SkipInstaller,
    [string]$SecretFile = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\.."))
$version = (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "VERSION")).Trim()
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "VERSION must contain three numeric components: $version"
}

function Resolve-BuildPython {
    if ($env:INFINITE_CANVAS_PYTHON -and (Test-Path -LiteralPath $env:INFINITE_CANVAS_PYTHON)) {
        return [System.IO.Path]::GetFullPath($env:INFINITE_CANVAS_PYTHON)
    }
    $embedded = Join-Path $projectRoot "python\python.exe"
    if (Test-Path -LiteralPath $embedded) {
        return $embedded
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    throw "Python 3.10 or newer is required. Set INFINITE_CANVAS_PYTHON to python.exe."
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Arguments -join ' ')"
    }
}

function Remove-VerifiedBuildDirectory {
    param([string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the project: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

$python = Resolve-BuildPython
Write-Host "Building InfiniteCanvas $version with $python"

if ($InstallDependencies) {
    Invoke-Checked $python @("-m", "pip", "install", "--no-cache-dir", "-r", (Join-Path $projectRoot "requirements.txt"), "-r", (Join-Path $projectRoot "requirements-desktop.txt"))
}

Invoke-Checked $python @((Join-Path $scriptDir "make_icon.py"), "--root", $projectRoot)
Invoke-Checked $python @("-m", "unittest", "discover", "-s", (Join-Path $projectRoot "tests"), "-p", "test_*.py", "-v")

Remove-VerifiedBuildDirectory (Join-Path $projectRoot "build\pyinstaller")
Remove-VerifiedBuildDirectory (Join-Path $projectRoot "dist\InfiniteCanvas")

Invoke-Checked $python @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--distpath", (Join-Path $projectRoot "dist"),
    "--workpath", (Join-Path $projectRoot "build\pyinstaller"),
    (Join-Path $scriptDir "InfiniteCanvas.spec")
)

$verifyArgs = @(
    (Join-Path $scriptDir "verify_release.py"),
    (Join-Path $projectRoot "dist\InfiniteCanvas"),
    "--version-file", (Join-Path $projectRoot "VERSION"),
    "--manifest", (Join-Path $projectRoot "dist\release-manifest.json")
)
if ($SecretFile) {
    $verifyArgs += @("--secret-file", $SecretFile)
}
Invoke-Checked $python $verifyArgs

if (-not $SkipInstaller) {
    $installerScript = Join-Path $scriptDir "InfiniteCanvas.iss"
    if (-not (Test-Path -LiteralPath $installerScript)) {
        throw "Installer definition is missing: $installerScript"
    }
    $isccPath = if ($env:INNO_SETUP_ISCC -and (Test-Path -LiteralPath $env:INNO_SETUP_ISCC)) {
        [System.IO.Path]::GetFullPath($env:INNO_SETUP_ISCC)
    } else {
        ""
    }
    $isccCommand = if (-not $isccPath) { Get-Command ISCC.exe -ErrorAction SilentlyContinue } else { $null }
    if ($isccCommand) {
        $isccPath = $isccCommand.Source
    }
    if (-not $isccPath) {
        $standardIscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $standardIscc) {
            $isccPath = $standardIscc
        }
    }
    if (-not $isccPath) {
        throw "Inno Setup 6 is required. Install it with: winget install JRSoftware.InnoSetup"
    }
    Invoke-Checked $isccPath @(
        "/DAppVersion=$version",
        "/DSourceDir=$(Join-Path $projectRoot 'dist\InfiniteCanvas')",
        "/DOutputDir=$(Join-Path $projectRoot 'dist\installer')",
        $installerScript
    )
    $installer = Join-Path $projectRoot "dist\installer\InfiniteCanvas-Setup-$version.exe"
    if (-not (Test-Path -LiteralPath $installer)) {
        throw "Expected installer was not created: $installer"
    }
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $projectRoot "dist\installer\SHA256SUMS.txt") -Value "$hash  $(Split-Path -Leaf $installer)" -Encoding ascii
}

Write-Host "Build completed for InfiniteCanvas $version"
