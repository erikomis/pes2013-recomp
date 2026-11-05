# Shared settings for the shell scripts in tools/. Sourced, not run (zsh).
#
#   PES_ROOT       this repository (default: the parent of tools/)
#   PS3RECOMP_DIR  the toolkit checkout (default: ../ps3recomp-up-r8)
#   PES_GAME       the game's files and the decrypted EBOOT (default:
#                  $PES_ROOT/game): EBOOT.elf, EBOOT.BIN, PARAM.SFO
#   PES_EBOOT      the decrypted PPU ELF the loader and lifter read
#   Disc data      the ISO stays in ~/Downloads behind $PES_ROOT/game_iso;
#                  run.sh mounts it read-only and links PS3_GAME into the VFS
#   PY             the shared venv (nothing is installed by these scripts;
#                  if it is missing run ../deadpool-recomp/tools/setup.sh or
#                  set PY yourself). The launcher's install sets PS3RECOMP_DIR,
#                  PES_VENV and PES_KEYS to folders in its own data folder.
export PES_ROOT=${PES_ROOT:-${0:A:h:h}}
export PS3RECOMP_DIR=${PS3RECOMP_DIR:-$PES_ROOT/../ps3recomp-up-r8}
export PES_GAME=${PES_GAME:-$PES_ROOT/game}
export PES_EBOOT=${PES_EBOOT:-$PES_GAME/EBOOT.elf}
export PES_EBOOT_BIN=${PES_EBOOT_BIN:-$PES_GAME/EBOOT.BIN}
export PES_TITLE_ID=BLUS31029
export PES_ANALYSIS=${PES_ANALYSIS:-$PES_ROOT/analysis/BLUS31029}
export PES_RECOMP=${PES_RECOMP:-$PES_ROOT/recompiled/BLUS31029}
export PES_BUILD=${PES_BUILD:-$PES_ROOT/build/BLUS31029}
# The disc image behind the game_iso symlink; mounted read-only by run.sh.
export PES_ISO_DIR=${PES_ISO_DIR:-$PES_ROOT/game_iso}
export PES_MOUNT=${PES_MOUNT:-$HOME/mnt_pes13}
# Key file for decrypt_self.py. The 1.04 update is an NPDRM SELF (rev 0x19, free
# licence, no .rap), and Deadpool's older key file stops at NPDRM 0x1C, so write
# this one with: ../deadpool-recomp/tools/fetch_keys.py --out <the path below>.
if [[ -z ${PES_KEYS:-} ]]; then
    if [[ -f "$PES_ROOT/tools/self_keys.txt" ]]; then
        PES_KEYS=$PES_ROOT/tools/self_keys.txt
    elif [[ -d "$HOME/Library/Application Support/pes13-recomp/keys" ]]; then
        PES_KEYS="$HOME/Library/Application Support/pes13-recomp/keys/self_keys.txt"
    else
        PES_KEYS="$HOME/Desktop/deadpool-recomp/tools/self_keys.txt"
    fi
fi
export PES_KEYS
# The VFS tree run.sh assembles: the discs's PS3_GAME, plus the save tree the
# title creates under this repo, not under RPCS3's install.
export PES_VFS_ROOT=${PES_VFS_ROOT:-$PES_ROOT/rpcs3/dev_hdd0/disc/BLUS31029}
export PES_VENV=${PES_VENV:-$PES_ROOT/../deadpool-recomp/tools/.venv}
export PY=${PY:-$PES_VENV/bin/python}
