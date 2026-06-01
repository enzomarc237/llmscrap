$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonRoot = Join-Path $repoRoot "python"
$venvDir = Join-Path $pythonRoot ".venv-sidecar"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"

if (-not (Test-Path $venvPython)) {
    python -m venv $venvDir
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $pythonRoot "requirements.txt")
& $venvPython -m pip install pyinstaller
& $venvPython -m pip install $pythonRoot

$entryScript = Join-Path $pythonRoot "_sidecar_entry.py"
@'
from llmscrap.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
'@ | Set-Content -Path $entryScript -Encoding ascii

$distDir = Join-Path $pythonRoot "dist-sidecar"
$buildDir = Join-Path $pythonRoot "build-sidecar"

if (Test-Path $distDir) {
    Remove-Item $distDir -Recurse -Force
}
if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
}

& $venvPython -m PyInstaller `
    --noconfirm `
    --onefile `
    --name llmscrap-cli `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $buildDir `
    $entryScript

$targetTriple = if ($env:TAURI_ENV_TARGET_TRIPLE) {
    $env:TAURI_ENV_TARGET_TRIPLE
} elseif ($env:CARGO_BUILD_TARGET) {
    $env:CARGO_BUILD_TARGET
} else {
    "x86_64-pc-windows-msvc"
}

$binariesDir = Join-Path $repoRoot "src-tauri\\binaries"
New-Item -Path $binariesDir -ItemType Directory -Force | Out-Null

$sidecarSrc = Join-Path $distDir "llmscrap-cli.exe"
$sidecarDst = Join-Path $binariesDir ("llmscrap-cli-" + $targetTriple + ".exe")
Copy-Item -Path $sidecarSrc -Destination $sidecarDst -Force

if (Test-Path $entryScript) {
    Remove-Item $entryScript -Force
}
