param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDir,
    [Parameter(Mandatory = $true)]
    [string]$TestRoot,
    [string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\.."))
$sourceDirResolved = [System.IO.Path]::GetFullPath($SourceDir)
$testRootResolved = [System.IO.Path]::GetFullPath($TestRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$testRootPathRoot = [System.IO.Path]::GetPathRoot($testRootResolved).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)

if ($testRootResolved -eq $testRootPathRoot) {
    throw "TestRoot must not be a drive root: $testRootResolved"
}
if (-not (Test-Path -LiteralPath (Join-Path $sourceDirResolved "InfiniteCanvas.exe") -PathType Leaf)) {
    throw "SourceDir does not contain InfiniteCanvas.exe: $sourceDirResolved"
}

function Assert-WithinTestRoot {
    param([string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $prefix = $testRootResolved + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside TestRoot: $resolved"
    }
    return $resolved
}

function Remove-VerifiedPath {
    param([string]$Path)

    $resolved = Assert-WithinTestRoot $Path
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Arguments -join ' ')"
    }
}

function Invoke-SetupAndWait {
    param([string]$Installer, [string[]]$Arguments)

    $process = Start-Process -FilePath $Installer -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Installer failed with exit code $($process.ExitCode): $Installer"
    }
}

if (-not $IsccPath) {
    if ($env:INNO_SETUP_ISCC -and (Test-Path -LiteralPath $env:INNO_SETUP_ISCC)) {
        $IsccPath = $env:INNO_SETUP_ISCC
    } else {
        $isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($isccCommand) {
            $IsccPath = $isccCommand.Source
        }
    }
}
if (-not $IsccPath) {
    $standardIscc = "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $standardIscc) {
        $IsccPath = $standardIscc
    }
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) {
    throw "Inno Setup 6 compiler was not found. Pass -IsccPath or set INNO_SETUP_ISCC."
}

$version = (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "VERSION")).Trim()
$installerScript = Join-Path $scriptDir "InfiniteCanvas.iss"
$outputDir = Assert-WithinTestRoot (Join-Path $testRootResolved "installer")
$installRoot = Assert-WithinTestRoot (Join-Path $testRootResolved "app")
$userDataRoot = Assert-WithinTestRoot (Join-Path $testRootResolved "user-data\InfiniteCanvas")

New-Item -ItemType Directory -Path $testRootResolved -Force | Out-Null
Remove-VerifiedPath $outputDir
Remove-VerifiedPath $installRoot
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
New-Item -ItemType Directory -Path $userDataRoot -Force | Out-Null

$userDataSentinel = Join-Path $userDataRoot "upgrade-sentinel.txt"
$sentinelContents = "preserve-user-data-$version"
Set-Content -LiteralPath $userDataSentinel -Value $sentinelContents -Encoding ascii

Invoke-Checked $IsccPath @(
    "/DAppVersion=$version",
    "/DSourceDir=$sourceDirResolved",
    "/DOutputDir=$outputDir",
    "/DSmokeTestRoot=$installRoot",
    $installerScript
)

$installer = Join-Path $outputDir "InfiniteCanvas-Setup-$version.exe"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Smoke installer was not created: $installer"
}

$firstInstallLog = Assert-WithinTestRoot (Join-Path $testRootResolved "first-install.log")
Invoke-SetupAndWait $installer @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/LOG=`"$firstInstallLog`""
)

$installedExecutable = Join-Path $installRoot "InfiniteCanvas.exe"
if (-not (Test-Path -LiteralPath $installedExecutable -PathType Leaf)) {
    throw "Clean installation did not create InfiniteCanvas.exe"
}

$legacyWebsockets = Assert-WithinTestRoot (Join-Path $installRoot "_internal\websockets\legacy-speedups.cp310-win_amd64.pyd")
$legacyDistInfo = Assert-WithinTestRoot (Join-Path $installRoot "_internal\websockets-16.1.1.dist-info\legacy.txt")
New-Item -ItemType Directory -Path (Split-Path -Parent $legacyWebsockets) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $legacyDistInfo) -Force | Out-Null
Set-Content -LiteralPath $legacyWebsockets -Value "legacy-python-310" -Encoding ascii
Set-Content -LiteralPath $legacyDistInfo -Value "legacy-dist-info" -Encoding ascii

$upgradeLog = Assert-WithinTestRoot (Join-Path $testRootResolved "upgrade-install.log")
Invoke-SetupAndWait $installer @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/LOG=`"$upgradeLog`""
)

if (Test-Path -LiteralPath $legacyWebsockets) {
    throw "Legacy websockets binary survived the upgrade: $legacyWebsockets"
}
if (Test-Path -LiteralPath $legacyDistInfo) {
    throw "Legacy websockets dist-info survived the upgrade: $legacyDistInfo"
}
if (-not (Test-Path -LiteralPath $installedExecutable -PathType Leaf)) {
    throw "Upgrade did not restore InfiniteCanvas.exe"
}
$preservedContents = (Get-Content -Raw -LiteralPath $userDataSentinel).Trim()
if ($preservedContents -ne $sentinelContents) {
    throw "User-data sentinel changed during the upgrade smoke test"
}

Write-Host "Installer smoke test passed: clean install and legacy-runtime upgrade"
