#!/bin/zsh
# Standalone isolated profile: does not invoke run.sh's shared-tree setup.
set -eu
export PES_ROOT=${0:A:h:h}
source "$PES_ROOT/tools/env.sh"
profile="$PES_ROOT/analysis/test-save-brasil-2026"
if [[ ! -f "$profile/manifest.json" || ! -d "$PES_VFS_ROOT/PS3_GAME" ]]; then
    print -u2 'Perfil de teste ou disco montado ausente. Consulte docs/SAVE_BRASIL_2026.md.'
    exit 1
fi
export PS3_VFS_ROOT="$PES_VFS_ROOT"
export PS3_GAMEDATA_ROOT="$profile/gamedata"
export PS3_HDD1_ROOT="$profile/hdd1"
export PS3_EDAT_CACHE="$PES_ROOT/cache/edat"
export RSX_MSL_CACHE="$PES_ROOT/cache/msl"
export PS3_LANG=PT
export PS3_VERBOSE=0
export PS3_ANISO=${PS3_ANISO:-16}
export PS3_TITLE='PES 2013 — TESTE Brasil 2026'
if [[ -d "$HOME/Library/Application Support/rpcs3/dev_flash" ]]; then
    export PS3_DEV_FLASH="$HOME/Library/Application Support/rpcs3/dev_flash"
fi
unset PS3_MODS PS3_MODS_DIR PS3_MODS_DUMP
cd "$PES_ROOT"
print 'TESTE: 27 clubes com listas/nomes/números 2026; posições, faces e atributos antigos.'
print 'Todos os salvamentos desta execução ficam no perfil separado em analysis/.'
exec "$PES_BUILD/PES2013Recomp" "$PES_EBOOT"
