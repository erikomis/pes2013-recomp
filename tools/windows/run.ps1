# Run the recompiled PES 2013 on Windows. Extra arguments are VAR=value
# environment overrides, as with tools/run.sh on macOS:
#
#   powershell -ExecutionPolicy Bypass -File tools\windows\run.ps1 [VAR=value ...]
#   ... run.ps1 PS3RECOMP_VK_FULLSCREEN=1 RSX_PACE_LOG=5
#
# PES 2013 is a disc title. The disc image is mounted read-only (Mount-DiskImage)
# unless PES_DISC_DIR names a folder that already holds PS3_GAME, and the game's
# file tree is assembled under rpcs3\dev_hdd0\disc\BLUS31029 with directory
# junctions (no administrator rights or Developer Mode needed) and copies of the
# few single files. Saves land under this repository's rpcs3\dev_hdd0\home tree.
#
# The game's output goes to cache\boot-last.log; PES_LOG=<file> sends it
# elsewhere and PES_LOG=- keeps it on this console.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Overrides)
. "$PSScriptRoot\env.ps1"
$root = $script:PES_ROOT
$exe = Join-Path $script:PES_BUILD 'PES2013Recomp.exe'
if (-not (Test-Path $exe)) { throw "not built yet: $exe (run tools\windows\rebuild.ps1)" }
if (-not (Test-Path $script:PES_EBOOT)) { throw "no decrypted EBOOT: $($script:PES_EBOOT) (run tools\windows\rebuild.ps1 decrypt)" }

# ---- the disc ------------------------------------------------------------
$disc = $env:PES_DISC_DIR
if (-not $disc) {
    $iso = $env:PES_ISO
    if (-not $iso) {
        $iso = Get-ChildItem -Path (Join-Path $root 'game_iso') -Filter *.iso -ErrorAction SilentlyContinue |
               Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $iso -or -not (Test-Path $iso)) {
        throw 'no disc: put the BLUS31029 .iso in game_iso\, or set PES_ISO=<file.iso>, or PES_DISC_DIR=<folder with PS3_GAME>'
    }
    $img = Get-DiskImage -ImagePath $iso
    if (-not $img.Attached) {
        Say "mounting $iso (read-only)"
        $img = Mount-DiskImage -ImagePath $iso -Access ReadOnly -StorageType ISO -PassThru
    }
    $letter = ($img | Get-Volume).DriveLetter
    if (-not $letter) { throw "the image is mounted but has no drive letter: $iso" }
    $disc = "${letter}:\"
}
if (-not (Test-Path (Join-Path $disc 'PS3_GAME'))) { throw "no PS3_GAME in $disc" }

# ---- the VFS tree --------------------------------------------------------
# Directories are junctions to their source; files are copied (a file symlink
# needs Developer Mode, and a hard link cannot leave the volume).
function Set-Junction([string]$link, [string]$target) {
    if (Test-Path $link) {
        $it = Get-Item $link -Force
        if ($it.LinkType -eq 'Junction' -and ($it.Target -join '') -eq $target) { return }
        if ($it.LinkType) { cmd /c rmdir "`"$link`"" | Out-Null }
        else { throw "$link exists and is not a junction; move it away" }
    }
    New-Item -ItemType Directory -Force (Split-Path $link -Parent) | Out-Null
    cmd /c mklink /J "`"$link`"" "`"$target`"" | Out-Null
    if ($LASTEXITCODE) { throw "could not make the junction $link -> $target" }
}
function Copy-IfNewer([string]$src, [string]$dst) {
    if (-not (Test-Path $src)) { return }
    if ((Test-Path $dst) -and (Get-Item $dst).Length -eq (Get-Item $src).Length -and
        (Get-Item $dst).LastWriteTimeUtc -ge (Get-Item $src).LastWriteTimeUtc) { return }
    New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
    Copy-Item -Force $src $dst
}

$vfs = $script:PES_VFS_ROOT
$tid = $script:PES_TITLE_ID
New-Item -ItemType Directory -Force $vfs, (Join-Path $root 'rpcs3\dev_hdd0\home\00000001') | Out-Null
Copy-IfNewer (Join-Path $disc 'PS3_DISC.SFB') (Join-Path $vfs 'PS3_DISC.SFB')
Set-Junction (Join-Path $vfs 'PS3_GAME') (Join-Path $disc 'PS3_GAME')
if (Test-Path (Join-Path $disc 'PS3_UPDATE')) { Set-Junction (Join-Path $vfs 'PS3_UPDATE') (Join-Path $disc 'PS3_UPDATE') }

# The game checks for its "installed game data" under the savedata root and will
# not stream its .img archives without it. The disc USRDIR holds the same files,
# so the install slot points there. The download slot is Data Pack 6, whose
# dt0f.img replaces the disc's (see tools/run.sh).
Set-Junction (Join-Path $vfs "game\${tid}_INSTALL\USRDIR") (Join-Path $disc 'PS3_GAME\USRDIR')
$pack = Join-Path $root "${tid}_DOWNLOAD"
if (Test-Path (Join-Path $pack 'USRDIR')) {
    Set-Junction (Join-Path $vfs "game\${tid}_DOWNLOAD\USRDIR") (Join-Path $pack 'USRDIR')
    Copy-IfNewer (Join-Path $pack 'PARAM.SFO') (Join-Path $vfs "game\${tid}_DOWNLOAD\PARAM.SFO")
} else {
    Set-Junction (Join-Path $vfs "game\${tid}_DOWNLOAD\USRDIR") (Join-Path $disc 'PS3_GAME\USRDIR')
}
# The 1.04 update, where its PKG installs it on a console.
Copy-IfNewer (Join-Path $script:PES_GAME 'PARAM.SFO') (Join-Path $vfs "game\$tid\PARAM.SFO")
Copy-IfNewer $script:PES_EBOOT_BIN (Join-Path $vfs "game\$tid\USRDIR\EBOOT.BIN")

# ---- environment ---------------------------------------------------------
function Set-Default([string]$name, [string]$value) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { Set-Item "env:$name" $value }
}
$env:PS3_VFS_ROOT = $vfs
# /dev_hdd1, the cache partition: without a writable root the title's first
# cache write fails and its system-cache thread exits (the boot screen hangs).
Set-Default 'PS3_HDD1_ROOT' (Join-Path $root 'rpcs3\dev_hdd1')
New-Item -ItemType Directory -Force (Join-Path $env:PS3_HDD1_ROOT 'cache') | Out-Null
# cellSaveData appends \dev_hdd0\home\00000001\savedata to this.
Set-Default 'PS3_GAMEDATA_ROOT' (Join-Path $root 'rpcs3')
New-Item -ItemType Directory -Force (Join-Path $env:PS3_GAMEDATA_ROOT 'dev_hdd0\home\00000001\savedata') | Out-Null
Set-Default 'PS3_EDAT_CACHE' (Join-Path $root 'cache\edat')
# RPCS3's dev_flash (system fonts and modules), when there is one to borrow.
if (-not $env:PS3_DEV_FLASH) {
    $cands = @()
    if ($env:RPCS3_DIR) { $cands += (Join-Path $env:RPCS3_DIR 'dev_flash') }
    $cands += (Join-Path $env:APPDATA 'rpcs3\dev_flash')
    $cands += Get-ChildItem -Path (Split-Path $root -Parent) -Directory -ErrorAction SilentlyContinue |
              ForEach-Object { Join-Path $_.FullName 'RPCS3\dev_flash'; Join-Path $_.FullName 'rpcs3\dev_flash' }
    $df = $cands | Where-Object { Test-Path (Join-Path $_ 'sys') } | Select-Object -First 1
    if ($df) { $env:PS3_DEV_FLASH = $df }
}
Set-Default 'PS3_TITLE' 'PES 2013'
# Console language: Portuguese (7, "PT") gives Portuguese menu labels; the
# first-run wizard still asks for the game language once (see tools/run.sh).
Set-Default 'PS3_LANG' 'PT'
# A redirected stderr means verbose by default; millions of lines a match.
Set-Default 'PS3_VERBOSE' '0'
# The game's audio threads at the host's top normal priority (tools/run.sh).
Set-Default 'PS3_PPU_BOOST_BELOW' '450'
# The MFC engine lookup memo, on every SPU channel access (the macOS build has
# its own always-on form of it).
Set-Default 'SPU_MFC_LOOKUP_CACHE' '1'
# The Vulkan backend: a window, and the guest's own vertex and fragment
# programs, which makes the shared register-file draw engine (the one the Metal
# build uses) the rendering path.
Set-Default 'PS3RECOMP_VK_WINDOW' '1'
Set-Default 'PS3RECOMP_VK_GUEST_PROGRAMS' '1'
# The engine's draws recorded into one submission instead of one submit and
# wait per draw: the training ground went from about 30 fps (FIFO drain 30-90 ms
# a frame) to 60 (2026-11-27, RTX 4070 Ti SUPER). VK_DRAW_BATCH=0 for the old path.
Set-Default 'VK_DRAW_BATCH' '1'
# Anisotropic filtering where the game minifies through mipmaps (the pitch at a
# distance), as the macOS build's default. PS3_ANISO=0 restores the game's own.
Set-Default 'PS3_ANISO' '16'
# HLSL -> SPIR-V translations kept on disk: a shader seen once is not
# translated again on the RSX thread in a later session.
Set-Default 'PS3RECOMP_SPIRV_CACHE' (Join-Path $root 'cache\spirv')
New-Item -ItemType Directory -Force $env:PS3RECOMP_SPIRV_CACHE | Out-Null
$env:PES_ROOT = $root

foreach ($o in $Overrides) {
    if ($o -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] }
    else { throw "not VAR=value: $o" }
}

# ---- run -----------------------------------------------------------------
$log = if ($env:PES_LOG) { $env:PES_LOG } else { Join-Path $root 'cache\boot-last.log' }
Say "PES 2013: $exe"
Say "disc $disc, saves $($env:PS3_GAMEDATA_ROOT)\dev_hdd0\home\00000001\savedata, dev_flash $(if ($env:PS3_DEV_FLASH) { $env:PS3_DEV_FLASH } else { '(none)' })"
if ($log -eq '-') {
    & $exe $script:PES_EBOOT
    exit $LASTEXITCODE
}
New-Item -ItemType Directory -Force (Split-Path $log -Parent) | Out-Null
Say "log: $log"
cmd /c "`"$exe`" `"$($script:PES_EBOOT)`" > `"$log`" 2>&1"
exit $LASTEXITCODE
