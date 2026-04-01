# Aura CLI Windows MSI Builder
# Requires: WiX Toolset v4+, Python 3.11+, PyInstaller

param(
    [string]$Version = "1.0.0",
    [string]$OutputDir = ".\dist",
    [switch]$Sign,
    [string]$CertThumbprint = ""
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Aura CLI Windows MSI Builder" -ForegroundColor Cyan
Write-Host "  Version: $Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Directories
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path "$ScriptDir\..\..\..\.."
$BuildDir = "$ScriptDir\build"
$SourceDir = "$BuildDir\source"

# Clean previous build
Write-Host "`n[1/6] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}
New-Item -ItemType Directory -Path $SourceDir -Force | Out-Null

# Build executable with PyInstaller
Write-Host "`n[2/6] Building executable with PyInstaller..." -ForegroundColor Yellow

$PyInstallerSpec = @"
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['$RepoRoot/src/cli/main.py'],
    pathex=['$RepoRoot'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.services.licensing',
        'src.services.licensing.license_service',
        'src.services.licensing.hardware_fingerprint',
        'src.services.licensing.offline_validator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='aura',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='$ScriptDir/assets/aura.ico',
    version='$ScriptDir/version_info.txt',
)
"@

$PyInstallerSpec | Out-File -FilePath "$BuildDir\aura.spec" -Encoding UTF8

# Create version info file
$VersionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($Version.Replace('.', ',')),0),
    prodvers=($($Version.Replace('.', ',')),0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'Aenea Labs'),
          StringStruct(u'FileDescription', u'Aura CLI'),
          StringStruct(u'FileVersion', u'$Version'),
          StringStruct(u'InternalName', u'aura'),
          StringStruct(u'LegalCopyright', u'Copyright (c) 2025 Aenea Labs'),
          StringStruct(u'OriginalFilename', u'aura.exe'),
          StringStruct(u'ProductName', u'Project Aura'),
          StringStruct(u'ProductVersion', u'$Version')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@

$VersionInfo | Out-File -FilePath "$ScriptDir\version_info.txt" -Encoding UTF8

# Run PyInstaller
Push-Location $BuildDir
try {
    python -m PyInstaller --clean --noconfirm aura.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed"
    }
} finally {
    Pop-Location
}

# Copy files to source directory
Write-Host "`n[3/6] Preparing installer source..." -ForegroundColor Yellow
Copy-Item "$BuildDir\dist\aura.exe" "$SourceDir\"
Copy-Item "$RepoRoot\LICENSE" "$SourceDir\LICENSE.txt"
Copy-Item "$RepoRoot\README.md" "$SourceDir\"

# Create assets directory if needed
$AssetsDir = "$ScriptDir\assets"
if (-not (Test-Path $AssetsDir)) {
    New-Item -ItemType Directory -Path $AssetsDir -Force | Out-Null
}

# Create placeholder license RTF if not exists
if (-not (Test-Path "$SourceDir\license.rtf")) {
    $LicenseRtf = @"
{\rtf1\ansi\deff0
{\fonttbl{\f0 Arial;}}
\f0\fs20
Project Aura - End User License Agreement\par
\par
Copyright (c) 2025 Aenea Labs\par
\par
This software is provided under the terms of your license agreement with Aenea Labs.
}
"@
    $LicenseRtf | Out-File -FilePath "$SourceDir\license.rtf" -Encoding ASCII
}

# Build MSI with WiX
Write-Host "`n[4/6] Building MSI with WiX..." -ForegroundColor Yellow

$WixArgs = @(
    "build",
    "$ScriptDir\aura.wxs",
    "-d", "SourceDir=$SourceDir",
    "-d", "Version=$Version",
    "-arch", "x64",
    "-o", "$BuildDir\aura-cli-$Version-windows-x64.msi"
)

wix @WixArgs

if ($LASTEXITCODE -ne 0) {
    throw "WiX build failed"
}

# Sign MSI if requested
if ($Sign) {
    Write-Host "`n[5/6] Signing MSI..." -ForegroundColor Yellow

    if (-not $CertThumbprint) {
        throw "Certificate thumbprint required for signing"
    }

    $SignArgs = @(
        "sign",
        "/sha1", $CertThumbprint,
        "/fd", "SHA256",
        "/tr", "http://timestamp.digicert.com",
        "/td", "SHA256",
        "/d", "Aura CLI",
        "$BuildDir\aura-cli-$Version-windows-x64.msi"
    )

    signtool @SignArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed"
    }
} else {
    Write-Host "`n[5/6] Skipping signing (use -Sign to enable)" -ForegroundColor Yellow
}

# Copy to output
Write-Host "`n[6/6] Copying to output directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
Copy-Item "$BuildDir\aura-cli-$Version-windows-x64.msi" "$OutputDir\"

# Generate checksums
$MsiPath = "$OutputDir\aura-cli-$Version-windows-x64.msi"
$Hash = (Get-FileHash -Path $MsiPath -Algorithm SHA256).Hash
"$Hash  aura-cli-$Version-windows-x64.msi" | Out-File -FilePath "$OutputDir\SHA256SUMS.txt" -Append

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "  Output: $MsiPath" -ForegroundColor Green
Write-Host "  SHA256: $Hash" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
