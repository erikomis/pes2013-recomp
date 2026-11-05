#!/bin/zsh
# Rebuild the PES 2013 port: decrypt, analyse, lift, build.
#
#   tools/rebuild.sh [step ...]
#
# Steps, in order (default: all of them): decrypt analyse lift spu build
#
#   decrypt  decrypts game/EBOOT.BIN (the 1.04 update from the PKG: NPDRM SELF,
#            key_rev 0x0019, free licence, no .rap) into game/EBOOT.elf with
#            $PS3RECOMP_DIR neighbour Deadpool's decrypt_self.py and the key
#            file from $PES_KEYS. Skipped when EBOOT.elf is already there.
#   analyse  toolkit tools/ppu_loader.py -> analysis/BLUS31029
#   lift     toolkit tools/ppu_lifter.py -> recompiled/BLUS31029
#   spu      tools/lift_spu.sh and tools/lift_jobs.sh -> port/spu
#   build    configure once if needed, then tools/build.sh (resource guards)
#
# Environment: see tools/env.sh. JOBS controls lifting; BUILD_JOBS controls build.
set -e
here=${0:A:h}; source "$here/env.sh"
E=$PES_EBOOT
if (( $# )); then steps=("$@"); else steps=(decrypt analyse lift spu build); fi
jobs=(); [ -n "$JOBS" ] && jobs=(-j "$JOBS")

say() { print -P "%B==> $*%b"; }

for s in $steps; do
    case $s in
    decrypt)
        say "decrypt"
        if [ ! -f "$E" ]; then
            [ -f "$PES_EBOOT_BIN" ] || {
                echo "EBOOT.BIN not found: $PES_EBOOT_BIN (stage it from the disc first)" >&2; exit 1; }
            [ -f "$PES_KEYS" ] || {
                echo "no key file: $PES_KEYS (run ../deadpool-recomp/tools/fetch_keys.py first)" >&2; exit 1; }
            "$PY" "$PES_ROOT/../deadpool-recomp/tools/decrypt_self.py" "$PES_EBOOT_BIN" \
                -o "$E" --keys "$PES_KEYS" || exit 1
        fi
        [ "$(head -c 4 "$E")" = $'\x7fELF' ] || { echo "$E is not an ELF" >&2; exit 1; }
        echo "  $E: $(shasum -a 256 "$E" | cut -d' ' -f1)" ;;
    analyse)
        say "analyse"
        "$PY" "$PS3RECOMP_DIR/tools/ppu_loader.py" "$E" -o "$PES_ANALYSIS" ;;
    lift)
        say "lift"
        "$PY" "$PS3RECOMP_DIR/tools/ppu_lifter.py" "$E" "${jobs[@]}" --chunks 12 \
            --functions "$PES_ANALYSIS/EBOOT.functions.json" \
            --hle-stubs "$PES_ANALYSIS/EBOOT.imports.json" \
            --output "$PES_RECOMP" ;;
    spu)
        say "spu"
        "$PY" "$PS3RECOMP_DIR/tools/extract_spu_images.py" "$E" -o "$PES_ANALYSIS/spu"
        "$here/lift_spu.sh"
        "$here/lift_jobs.sh" ;;
    build)
        say "build"
        if [ ! -f "$PES_BUILD/build.ninja" ]; then
            cmake -S "$PES_ROOT/port" -B "$PES_BUILD" -G Ninja \
                  -DPS3RECOMP_DIR="$PS3RECOMP_DIR" -DRECOMP_DIR="$PES_RECOMP" \
                  -DPython3_EXECUTABLE="$PY"
        fi
        "$here/build.sh" --check
        "$here/build.sh"
        echo ""
        echo "run it:"
        echo "  tools/run.sh" ;;
    *)
        echo "unknown step '$s' (decrypt analyse lift spu build)" >&2; exit 2 ;;
    esac
done
say "done"
