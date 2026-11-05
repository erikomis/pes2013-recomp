#!/bin/zsh
# Run the recompiled PES 2013 build. Extra arguments are passed through as
# VAR=value environment overrides, e.g.  tools/run.sh PS3_MON=1
#
# PES 2013 is a disc title, so the runner needs the disc structure and the
# ISO mounts read-only when it is not mounted yet. Saves land under this
# repo's rpcs3/dev_hdd0/home tree, not in RPCS3's install.
set -e
source "${0:A:h}/env.sh"

# Mount the disc image read-only if no previous mount is live.
if [ ! -d "$PES_MOUNT/PS3_GAME" ]; then
    iso=("$PES_ISO_DIR"/*.iso(N))
    [ -f "$iso[1]" ] || { echo "ISO not found under $PES_ISO_DIR (check game_iso symlink)" >&2; exit 1; }
    mkdir -p "$PES_MOUNT"
    hdiutil attach -readonly -mountpoint "$PES_MOUNT" "$iso[1]" || exit 1
fi

# VFS tree: local directories, then the disc contents by symlink only at the
# leaf level (never symlinked parents: AGENTS.md forbids a symlinked VFS root).
mkdir -p "$PES_VFS_ROOT" "$PES_ROOT/rpcs3/dev_hdd0/home/00000001"
ln -sfn "$PES_MOUNT/PS3_DISC.SFB" "$PES_VFS_ROOT/PS3_DISC.SFB"
ln -sfn "$PES_MOUNT/PS3_GAME" "$PES_VFS_ROOT/PS3_GAME"
ln -sfn "$PES_MOUNT/PS3_UPDATE" "$PES_VFS_ROOT/PS3_UPDATE"

# The game checks for its own "installed game data" under the savedata root and
# refuses to stream its asset archives (.img) without it. There is no HDD
# install on this machine, and the disc USRDIR already holds the same files, so
# point the install slot at it. Without this the loader fails its first big read
# and blocks the DMA manager forever. The download slot is data pack 6, whose
# dt0f.img replaces the disc's.
pack=$PES_ROOT/${PES_TITLE_ID}_DOWNLOAD
mkdir -p "$PES_VFS_ROOT/game/${PES_TITLE_ID}_INSTALL" "$PES_VFS_ROOT/game/${PES_TITLE_ID}_DOWNLOAD"
ln -sfn ../../PS3_GAME/USRDIR "$PES_VFS_ROOT/game/${PES_TITLE_ID}_INSTALL/USRDIR"
if [ -d "$pack/USRDIR" ]; then
    ln -sfn "$pack/USRDIR" "$PES_VFS_ROOT/game/${PES_TITLE_ID}_DOWNLOAD/USRDIR"
    ln -sfn "$pack/PARAM.SFO" "$PES_VFS_ROOT/game/${PES_TITLE_ID}_DOWNLOAD/PARAM.SFO"
else
    ln -sfn ../../PS3_GAME/USRDIR "$PES_VFS_ROOT/game/${PES_TITLE_ID}_DOWNLOAD/USRDIR"
fi
# The 1.04 update, where its PKG installs it on a console.
mkdir -p "$PES_VFS_ROOT/game/$PES_TITLE_ID/USRDIR"
ln -sfn "$PES_GAME/PARAM.SFO" "$PES_VFS_ROOT/game/$PES_TITLE_ID/PARAM.SFO"
ln -sfn "$PES_EBOOT_BIN" "$PES_VFS_ROOT/game/$PES_TITLE_ID/USRDIR/EBOOT.BIN"

export PS3_VFS_ROOT=$PES_VFS_ROOT
# /dev_hdd1 is the CACHE partition cellSysCacheMount mounts. Without a writable
# host root behind it the mount lands in the read-only disc tree, the title's
# first cache write fails and the thread it starts for it exits (PES 2013:
# ps3SystemCache dies on buffer.tmp and the boot screen never advances).
export PS3_HDD1_ROOT=${PS3_HDD1_ROOT:-$PES_ROOT/rpcs3/dev_hdd1}
mkdir -p "$PS3_HDD1_ROOT/cache"
# Where cellSaveData puts the player's saves. Unset, it is cwd-relative
# "./gamedata", which is what the header comment above promises it is not: saves
# landed in $PES_ROOT/gamedata (game-derived data in the project root). The
# runtime appends /dev_hdd0/home/00000001/savedata, so the root is rpcs3/.
export PS3_GAMEDATA_ROOT=${PS3_GAMEDATA_ROOT:-$PES_ROOT/rpcs3}
mkdir -p "$PS3_GAMEDATA_ROOT/dev_hdd0/home/00000001/savedata"
export PS3_EDAT_CACHE=${PS3_EDAT_CACHE:-$PES_ROOT/cache/edat}
export RSX_MSL_CACHE=${RSX_MSL_CACHE:-$PES_ROOT/cache/msl}
[ -d "$HOME/Library/Application Support/rpcs3/dev_flash" ] && \
    export PS3_DEV_FLASH="${PS3_DEV_FLASH:-$HOME/Library/Application Support/rpcs3/dev_flash}"
export PS3_TITLE=${PS3_TITLE:-"PES 2013"}
# Menu language. The host reports Portuguese-Brazil (17) and the title renders
# that as Spanish; CELL_SYSUTIL_LANG_PORTUGUESE (7, "PT") gives Portuguese menu
# labels instead. The language page of the first-run wizard still opens on
# "Español" (the list has no default from the system language), so pick
# "Português" once with DOWN then CROSS -- that choice is what cellSaveData keeps
# and what the in-game text follows. Override per run: tools/run.sh PS3_LANG=pt-br (or 17).
export PS3_LANG=${PS3_LANG:-PT}
# A redirected stderr means verbose by default (runtime/ps3_log.h): millions of lines
# per match through one FILE lock, on the guest threads. Pass PS3_VERBOSE=1 to debug.
export PS3_VERBOSE=${PS3_VERBOSE:-0}
# Improve minified/mipmapped textures at oblique angles. The Metal backend
# already supports this; point samplers and unmipped UI keep guest filtering.
# Set PS3_ANISO=0 to restore original filtering, or 8 to reduce GPU cost.
export PS3_ANISO=${PS3_ANISO:-16}
# Keep twice the audio queue (about 43 ms) and let the mixer wait for a late block,
# so a frame that runs long does not become a gap in the sound. AUDIO_ELASTIC=0 is
# the shorter queue (about 21 ms).
export AUDIO_ELASTIC=${AUDIO_ELASTIC:-1}
export PES_ROOT

exec env "$@" "$PES_BUILD/PES2013Recomp" "$PES_EBOOT"
