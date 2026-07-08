<#
.SYNOPSIS
    Builds the SplitPayPDF_Portable folder (copy-and-run, no install on target).

.DESCRIPTION
    Run this on a BUILD machine (with internet + a normal 64-bit python.org
    Python installed). The result is a self-contained folder that runs on any
    64-bit Windows 10/11 machine without Python, pip, admin rights or internet.

    Steps performed:
      1. Detect the build machine's Python (must be 64-bit, python.org build
         with tkinter/tcl - NOT the Windows Store version).
      2. Download the matching official "embeddable" Python ZIP from
         python.org (or use -EmbedZip for an offline pre-downloaded copy).
      3. Extract it to <output>\python and enable Lib\site-packages.
      4. Copy tkinter + Tcl/Tk from the build Python into the bundle
         (the embeddable distribution does not include them).
      5. pip-install requirements.txt into the bundle (pip runs on the
         build machine only, never on the target machine).
      6. Copy the app, launcher and docs; create data\ and logs\.
      7. Smoke-test the bundled runtime (import fitz, pandas, tkinter).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build_portable.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build_portable.ps1 `
        -PythonExe "C:\Python312\python.exe" -OutputDir "D:\SplitPayPDF_Portable"
#>
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "SplitPayPDF_Portable"),
    [string]$PythonExe = "",
    # Optional: path to a pre-downloaded python-<ver>-embed-amd64.zip
    # (must match the build Python's exact version). Enables offline builds.
    [string]$EmbedZip = ""
)

$ErrorActionPreference = "Stop"
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

$RepoRoot = $PSScriptRoot

# ---------- 1. Locate and validate the build Python ----------
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    throw "No Python found on this machine. Install 64-bit Python from python.org (default options include tcl/tk) or pass -PythonExe."
}

Step "Build Python: $PythonExe"
$infoJson = & $PythonExe -c "import sys,struct,json;print(json.dumps({'ver':'.'.join(map(str,sys.version_info[:3])),'bits':struct.calcsize('P')*8,'prefix':sys.prefix}))"
if ($LASTEXITCODE -ne 0) { throw "Could not query the build Python." }
$info = $infoJson | ConvertFrom-Json
Step "Version $($info.ver), $($info.bits)-bit, prefix: $($info.prefix)"

if ($info.bits -ne 64) {
    throw "Build Python is 32-bit. Install 64-bit Python (the target machines need 64-bit)."
}
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PythonExe -c "import tkinter" 2>$null | Out-Null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -ne 0) {
    throw "Build Python has no tkinter. Reinstall Python from python.org with the 'tcl/tk and IDLE' option enabled."
}
$tclSrc = Join-Path $info.prefix "tcl"
if (-not (Test-Path $tclSrc)) {
    throw "No 'tcl' folder in $($info.prefix). Windows Store Python is not supported - install Python from python.org."
}

# ---------- 2. Clean / create the output folder ----------
if (Test-Path $OutputDir) {
    $looksLikeBuild = (Test-Path (Join-Path $OutputDir "Run_SplitPayPDF.cmd")) -or
                      -not (Get-ChildItem -Force $OutputDir | Select-Object -First 1)
    if (-not $looksLikeBuild) {
        throw "$OutputDir exists and does not look like a previous build. Remove it manually or pass a different -OutputDir."
    }
    Step "Removing previous build: $OutputDir"
    Remove-Item $OutputDir -Recurse -Force
}
$PyDir  = Join-Path $OutputDir "python"
$AppDir = Join-Path $OutputDir "app"
Step "Creating folder structure in $OutputDir"
New-Item -ItemType Directory -Path $PyDir, $AppDir,
    (Join-Path $OutputDir "data"), (Join-Path $OutputDir "logs") | Out-Null

# ---------- 3. Obtain and extract the embeddable Python ----------
if (-not $EmbedZip) {
    $zipName  = "python-$($info.ver)-embed-amd64.zip"
    $url      = "https://www.python.org/ftp/python/$($info.ver)/$zipName"
    $EmbedZip = Join-Path $env:TEMP $zipName
    if (Test-Path $EmbedZip) {
        Step "Using cached download: $EmbedZip"
    } else {
        Step "Downloading $url"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $EmbedZip
    }
} else {
    Step "Using provided embeddable ZIP: $EmbedZip"
    if (-not (Test-Path $EmbedZip)) { throw "Embeddable ZIP not found: $EmbedZip" }
}
Step "Extracting embeddable Python"
Expand-Archive -Path $EmbedZip -DestinationPath $PyDir -Force

# ---------- 4. Enable Lib / site-packages in the ._pth file ----------
$pth = Get-ChildItem $PyDir -Filter "python3*._pth" | Select-Object -First 1
if (-not $pth) { throw "No python3*._pth found in $PyDir - unexpected embeddable layout." }
Add-Content -Path $pth.FullName -Value "Lib`r`nLib\site-packages"
$SitePackages = Join-Path $PyDir "Lib\site-packages"
New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null

# ---------- 5. Copy tkinter + Tcl/Tk from the build Python ----------
Step "Copying tkinter + Tcl/Tk into the bundle"
Copy-Item (Join-Path $info.prefix "Lib\tkinter") (Join-Path $PyDir "Lib\tkinter") -Recurse
Copy-Item $tclSrc (Join-Path $PyDir "tcl") -Recurse
Get-ChildItem (Join-Path $info.prefix "DLLs") |
    Where-Object { $_.Name -match '^(_tkinter\.pyd|tcl\w*\.dll|tk\w*\.dll|zlib1\.dll)$' } |
    Copy-Item -Destination $PyDir

# ---------- 6. Install dependencies into the bundle ----------
Step "Installing dependencies (pip runs on THIS machine only)"
& $PythonExe -m pip install `
    --target $SitePackages `
    --only-binary=:all: `
    --no-warn-script-location `
    -r (Join-Path $RepoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

# ---------- 7. Copy app, launcher and docs ----------
Step "Copying application files"
foreach ($f in "SplitPayPDF.py", "splitpay_core.py", "requirements.txt", "README.md", "LICENSE") {
    $src = Join-Path $RepoRoot $f
    if (Test-Path $src) { Copy-Item $src $AppDir }
}
if (Test-Path (Join-Path $RepoRoot "images")) {
    Copy-Item (Join-Path $RepoRoot "images") (Join-Path $AppDir "images") -Recurse
}
Copy-Item (Join-Path $RepoRoot "packaging\Run_SplitPayPDF.cmd")  $OutputDir
Copy-Item (Join-Path $RepoRoot "packaging\README_PORTABLE.txt") $OutputDir
Copy-Item (Join-Path $RepoRoot "packaging\IT_SECURITY_NOTES.txt") $OutputDir
Set-Content (Join-Path $OutputDir "data\README.txt") `
    "Optional workspace for your input/output PDFs. The app does not require this folder."
Set-Content (Join-Path $OutputDir "logs\README.txt") `
    "Optional folder for exported logs. The app log itself is written to %APPDATA%\SplitPayPDF\app_log.txt."

# ---------- 8. Smoke test the bundled runtime ----------
Step "Smoke-testing the bundled runtime"
& (Join-Path $PyDir "python.exe") -c "import fitz, tkinter, ttkbootstrap, tkinterdnd2; print('  imports OK (fitz/tkinter/ttkbootstrap/tkinterdnd2)')"
if ($LASTEXITCODE -ne 0) { throw "Smoke test FAILED - the bundle is not usable." }

# ---------- Done ----------
$sizeMB = [math]::Round((Get-ChildItem $OutputDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host ""
Write-Host "BUILD OK -> $OutputDir  (~$sizeMB MB)" -ForegroundColor Green
Write-Host "Next: test Run_SplitPayPDF.cmd on this machine, then ZIP the folder and distribute."
