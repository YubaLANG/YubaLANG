param(
    [string]$Version = "latest",
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA "Programs\YubaLANG"),
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$repository = "yubalang/yubalang"
$executable = Join-Path $InstallDirectory "YubaLANG.exe"

function Remove-YubaLang {
    if (Test-Path -LiteralPath $executable) {
        Remove-Item -LiteralPath $executable -Force
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath) {
        $remaining = @(
            $userPath -split ";" | Where-Object {
                $_.TrimEnd("\") -ine $InstallDirectory.TrimEnd("\")
            }
        )
        [Environment]::SetEnvironmentVariable("Path", ($remaining -join ";"), "User")
        $env:Path = ($env:Path -split ";" | Where-Object {
            $_.TrimEnd("\") -ine $InstallDirectory.TrimEnd("\")
        }) -join ";"
    }
    Write-Output "Removed YubaLANG from $InstallDirectory"
}

if ($Uninstall) {
    Remove-YubaLang
    exit 0
}

if ($Version -ne "latest" -and $Version -notmatch "^v[0-9][A-Za-z0-9._-]*$") {
    throw "Version must be 'latest' or a version tag such as v1.2.0."
}

$archiveName = "YubaLANG-windows-x64.zip"
if ($Version -eq "latest") {
    $releaseUrl = "https://github.com/$repository/releases/latest/download"
} else {
    $releaseUrl = "https://github.com/$repository/releases/download/$Version"
}
$temporaryDirectory = Join-Path $env:TEMP ("yubalang-" + [guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
    $archivePath = Join-Path $temporaryDirectory $archiveName
    $checksumsPath = Join-Path $temporaryDirectory "SHA256SUMS"
    Invoke-WebRequest -Uri "$releaseUrl/$archiveName" -OutFile $archivePath
    Invoke-WebRequest -Uri "$releaseUrl/SHA256SUMS" -OutFile $checksumsPath

    $checksumLine = Get-Content -LiteralPath $checksumsPath | Where-Object {
        $_ -match ("^[0-9a-fA-F]{64}\s+\*?" + [regex]::Escape($archiveName) + "$")
    } | Select-Object -First 1
    if (-not $checksumLine) {
        throw "Checksum for $archiveName was not found in the release."
    }
    $expectedHash = ($checksumLine -split "\s+")[0]
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
    if ($actualHash -ine $expectedHash) {
        throw "Checksum verification failed for $archiveName."
    }

    $extractedDirectory = Join-Path $temporaryDirectory "extracted"
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractedDirectory
    $downloadedExecutable = Join-Path $extractedDirectory "YubaLANG.exe"
    if (-not (Test-Path -LiteralPath $downloadedExecutable)) {
        throw "Release archive does not contain YubaLANG.exe."
    }

    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    Copy-Item -LiteralPath $downloadedExecutable -Destination $executable -Force

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathEntries = @($userPath -split ";" | Where-Object { $_ })
    if (-not ($pathEntries | Where-Object {
        $_.TrimEnd("\") -ieq $InstallDirectory.TrimEnd("\")
    })) {
        $pathEntries += $InstallDirectory
        [Environment]::SetEnvironmentVariable("Path", ($pathEntries -join ";"), "User")
    }
    if (-not (($env:Path -split ";") | Where-Object {
        $_.TrimEnd("\") -ieq $InstallDirectory.TrimEnd("\")
    })) {
        $env:Path = "$InstallDirectory;$env:Path"
    }

    Write-Output "Installed YubaLANG to $executable"
    Write-Output "Open a new terminal, then run: YubaLANG.exe path\to\program.hl"
    Write-Warning "This executable is unsigned; Windows may display a SmartScreen warning."
} finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
