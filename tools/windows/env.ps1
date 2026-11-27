# Shared settings for the Windows scripts in tools/windows. Dot-sourced, not run:
#
#   . "$PSScriptRoot\env.ps1"
#
# Every path can be overridden from the environment before a script runs.
#
#   PES_ROOT        this repository (default: two folders above this one)
#   PS3RECOMP_DIR   the Windows toolkit checkout (default: ..\ps3recomp-pes-win,
#                   made by setup_toolkit.ps1; the macOS build keeps its own
#                   ..\ps3recomp-up-r8, which is a different base)
#   PES_GAME        EBOOT.BIN, PARAM.SFO, ICON0.PNG and PS3LOGO.DAT from the 01.04
#                   update PKG, and the decrypted EBOOT.elf (default: <repo>\game)
#   PES_ISO         the disc image (default: the first *.iso in <repo>\game_iso)
#   PES_DISC_DIR    instead of an image, a folder that holds PS3_GAME (a folder dump)
#   PES_KEYS        the key file for tools/decrypt_self.py (default:
#                   tools\self_keys.txt, else %APPDATA%\pes13-recomp\keys\self_keys.txt)
#   PES_VENV        the Python virtual environment (default: <repo>\.venv)
#   VCPKG_ROOT      a vcpkg checkout with sdl2[vulkan], glslang and vulkan-headers
#                   installed for x64-windows (default: the first of
#                   ..\vcpkg, %USERPROFILE%\vcpkg, C:\vcpkg that has them)
#   PES_BUILD       the build folder (default: <repo>\build\BLUS31029-win)

$ErrorActionPreference = 'Stop'

# tools\windows\local.ps1 (not committed): this machine's settings, as
# $env:NAME = 'value' lines for any variable above -- e.g. the disc image's
# path, or the analysis, lift and build folders on a drive with more room.
$local = Join-Path $PSScriptRoot 'local.ps1'
if (Test-Path $local) { . $local }

function Get-EnvOr([string]$name, [string]$default) {
    $v = [Environment]::GetEnvironmentVariable($name)
    if ($v) { return $v } else { return $default }
}

$script:PES_ROOT      = Get-EnvOr 'PES_ROOT' ((Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$script:PS3RECOMP_DIR = Get-EnvOr 'PS3RECOMP_DIR' (Join-Path (Split-Path $script:PES_ROOT -Parent) 'ps3recomp-pes-win')
$script:PES_GAME      = Get-EnvOr 'PES_GAME' (Join-Path $script:PES_ROOT 'game')
$script:PES_EBOOT     = Get-EnvOr 'PES_EBOOT' (Join-Path $script:PES_GAME 'EBOOT.elf')
$script:PES_EBOOT_BIN = Get-EnvOr 'PES_EBOOT_BIN' (Join-Path $script:PES_GAME 'EBOOT.BIN')
$script:PES_TITLE_ID  = 'BLUS31029'
$script:PES_ANALYSIS  = Get-EnvOr 'PES_ANALYSIS' (Join-Path $script:PES_ROOT 'analysis\BLUS31029')
$script:PES_RECOMP    = Get-EnvOr 'PES_RECOMP' (Join-Path $script:PES_ROOT 'recompiled\BLUS31029')
$script:PES_BUILD     = Get-EnvOr 'PES_BUILD' (Join-Path $script:PES_ROOT 'build\BLUS31029-win')
$script:PES_VFS_ROOT  = Get-EnvOr 'PES_VFS_ROOT' (Join-Path $script:PES_ROOT 'rpcs3\dev_hdd0\disc\BLUS31029')
$script:PES_VENV      = Get-EnvOr 'PES_VENV' (Join-Path $script:PES_ROOT '.venv')
$script:PY            = Get-EnvOr 'PY' (Join-Path $script:PES_VENV 'Scripts\python.exe')
# The toolkit's Python tools write their output in UTF-8, as on macOS (Python on
# Windows would use the ANSI code page).
$env:PYTHONUTF8 = '1'

if (-not $env:PES_KEYS) {
    $k1 = Join-Path $script:PES_ROOT 'tools\self_keys.txt'
    $k2 = Join-Path $env:APPDATA 'pes13-recomp\keys\self_keys.txt'
    $script:PES_KEYS = if (Test-Path $k1) { $k1 } else { $k2 }
} else { $script:PES_KEYS = $env:PES_KEYS }

# The toolkit the Windows build uses: sp00nznet/ps3recomp master at the commit
# below, plus this repository's toolkit changes merged onto it (the same ones
# patches/ps3recomp-675ed39-pes13.patch carries for macOS, and the Windows
# fixes), all in one patch. Upstream master already has the Vulkan backend on
# Windows, clang-cl builds, x86 SPU helpers and WASAPI audio.
$script:TOOLKIT_URL    = 'https://github.com/sp00nznet/ps3recomp.git'
$script:TOOLKIT_COMMIT = 'e85647a3'
$script:TOOLKIT_PATCH  = Join-Path $script:PES_ROOT 'patches\ps3recomp-e85647a-pes13-windows.patch'

# The VS 2022 Build Tools x64 environment and LLVM (clang-cl, lld-link) in this
# session. Taken from the inFAMOUS 2 port's tools/win_env.ps1.
function Import-BuildEnv {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { throw 'Visual Studio 2022 Build Tools not found (no vswhere.exe). Run tools\windows\install_deps.ps1.' }
    $vs = & $vswhere -products * -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'Visual Studio Build Tools has no C++ workload (Microsoft.VisualStudio.Component.VC.Tools.x86.x64).' }
    cmd /c "`"$vs\Common7\Tools\VsDevCmd.bat`" -arch=amd64 -host_arch=amd64 -no_logo >nul 2>nul && set" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] }
    }
    $llvm = Join-Path $env:ProgramFiles 'LLVM\bin'
    if (-not (Test-Path (Join-Path $llvm 'clang-cl.exe'))) { throw "LLVM (clang-cl) not found in $llvm. Run tools\windows\install_deps.ps1." }
    $env:Path = "$llvm;" + $env:Path
}

# A vcpkg tree that has what the Vulkan build needs.
function Find-Vcpkg {
    $cands = @()
    if ($env:VCPKG_ROOT) { $cands += $env:VCPKG_ROOT }
    $cands += (Join-Path (Split-Path $script:PES_ROOT -Parent) 'vcpkg')
    $cands += (Join-Path $env:USERPROFILE 'vcpkg')
    $cands += 'C:\vcpkg'
    # Another port's vcpkg beside this repository (..\<folder>\vcpkg), e.g. the
    # inFAMOUS 2 port's, which installs the same three packages.
    $cands += Get-ChildItem -Path (Split-Path $script:PES_ROOT -Parent) -Directory -ErrorAction SilentlyContinue |
              ForEach-Object { Join-Path $_.FullName 'vcpkg' }
    foreach ($c in $cands) {
        if ((Test-Path "$c\scripts\buildsystems\vcpkg.cmake") -and
            (Test-Path "$c\installed\x64-windows\include\SDL2\SDL.h") -and
            (Test-Path "$c\installed\x64-windows\include\vulkan\vulkan.h") -and
            (Test-Path "$c\installed\x64-windows\include\glslang")) { return $c }
    }
    return $null
}

function Say([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# Run a program with its stderr shown as text. Windows PowerShell 5.1 turns a
# native program's stderr line into an error record, which under
# $ErrorActionPreference = 'Stop' aborts the script even when the program
# succeeds (git and cmake print progress there). The exit code is left in
# $LASTEXITCODE for the caller to check. Plain $args, no param block: with named
# parameters PowerShell binds a program's own switches to them by prefix
# (git's -e to -Exe).
function Invoke-Exe {
    $exe = $args[0]
    $rest = @($args | Select-Object -Skip 1)
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $exe @rest 2>&1 | ForEach-Object { "$_" } }
    finally { $ErrorActionPreference = $eap }
}

# Invoke-Exe, and stop when the program fails.
function Invoke-Checked {
    Invoke-Exe @args
    if ($LASTEXITCODE) { throw "$($args[0]) failed (exit code $LASTEXITCODE): $(($args | Select-Object -Skip 1) -join ' ')" }
}
