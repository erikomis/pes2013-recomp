# Install what the Windows build needs, then the Python environment.
#
#   powershell -ExecutionPolicy Bypass -File tools\windows\install_deps.ps1 [-SkipWinget] [-Vcpkg DIR]
#
#   winget   Git, CMake, Ninja, Python 3.12, LLVM (clang-cl, lld-link) and the
#            Visual Studio 2022 Build Tools with the C++ workload. Already
#            installed packages are left as they are.
#   vcpkg    sdl2[vulkan], glslang and vulkan-headers for x64-windows, in an
#            existing vcpkg (VCPKG_ROOT, or one found as env.ps1 looks for it)
#            or a new one at -Vcpkg (default ..\vcpkg beside this repository).
#   .venv    the toolkit's Python requirements (pycryptodome, capstone, ...).
#
# The Vulkan loader itself (vulkan-1.dll) comes with the graphics driver.
# Reopen PowerShell after the first run if winget installed something, so the
# new PATH is seen.
param([switch]$SkipWinget, [string]$Vcpkg = '')
. "$PSScriptRoot\env.ps1"

if (-not $SkipWinget) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'winget not found: install "App Installer" from the Microsoft Store' }
    $pkgs = @(
        @{ id = 'Git.Git' },
        @{ id = 'Kitware.CMake' },
        @{ id = 'Ninja-build.Ninja' },
        @{ id = 'Python.Python.3.12' },
        @{ id = 'LLVM.LLVM' },
        @{ id = 'Microsoft.VisualStudio.2022.BuildTools';
           override = '--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended' }
    )
    foreach ($p in $pkgs) {
        Say "winget: $($p.id)"
        $a = @('install', '--id', $p.id, '--exact', '--accept-source-agreements', '--accept-package-agreements', '--silent')
        if ($p.override) { $a += @('--override', $p.override) }
        Invoke-Exe winget @a | Select-Object -Last 2
        # Already installed is not a failure (winget answers with a nonzero code).
    }
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

# ---- vcpkg -----------------------------------------------------------------
$vc = Find-Vcpkg
if ($vc) {
    Say "vcpkg with the packages already: $vc"
} else {
    $vc = if ($Vcpkg) { $Vcpkg } elseif ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { Join-Path (Split-Path $script:PES_ROOT -Parent) 'vcpkg' }
    if (-not (Test-Path "$vc\vcpkg.exe")) {
        if (-not (Test-Path "$vc\.git")) {
            Say "cloning vcpkg -> $vc"
            Invoke-Checked git clone --quiet https://github.com/microsoft/vcpkg.git $vc
        }
        Invoke-Checked "$vc\bootstrap-vcpkg.bat" -disableMetrics
    }
    Say 'vcpkg: sdl2[vulkan] glslang vulkan-headers (x64-windows)'
    Invoke-Checked "$vc\vcpkg.exe" install 'sdl2[vulkan]:x64-windows' 'glslang:x64-windows' 'vulkan-headers:x64-windows'
    Say "vcpkg ready: $vc (set VCPKG_ROOT=$vc if it is not found by itself)"
}

# ---- Python ----------------------------------------------------------------
if (-not (Test-Path $script:PY)) {
    $sys = Get-Command py -ErrorAction SilentlyContinue
    if ($sys) { Invoke-Checked py -3.12 -m venv $script:PES_VENV }
    else { Invoke-Checked python -m venv $script:PES_VENV }
}
$req = Join-Path $script:PS3RECOMP_DIR 'requirements.txt'
if (Test-Path $req) {
    Invoke-Checked $script:PY -m pip install --quiet --disable-pip-version-check -r $req
} else {
    # Before setup_toolkit.ps1: the same list, so decrypt works right away.
    Invoke-Checked $script:PY -m pip install --quiet --disable-pip-version-check 'pycryptodome>=3.19' 'capstone>=5.0' 'construct>=2.10' 'tabulate>=0.9' 'tqdm>=4.65'
}
Say "Python ready: $($script:PY)"
Say 'next: tools\windows\setup_toolkit.ps1, then tools\windows\rebuild.ps1'
