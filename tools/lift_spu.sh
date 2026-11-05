#!/bin/zsh
# Lift the SPU images embedded in the game's EBOOT and register them for the
# SPURS/workload dispatch (port/spu/spu_workloads.c).
#
#   tools/lift_spu.sh
#
# The embedded images are extracted SPU ELFs in analysis/BLUS31029/spu/ (regen
# with rebuild.sh); their file bytes are exactly the blobs the runtime
# fingerprints at dispatch time, so content fingerprints match.
#
# Three images embed a rodata/data tail inside their executable segment
# (version strings "32.081", tables, PCDI/PCER signatures). spu_lifter detects
# the tail as code (hundreds of `.word`), so lift those with --code-end at
# the end of the last real function (values found by disassembling the tail --
# everything from it on is data: zero padding, 0x01010101 filter tables, ASCII):
#   spu_0001 (35700 B):  code ends 0xb350
#   spu_0006 (137396 B): code ends 0x1e258
#   spu_0007 (145204 B): code ends 0x22fd0
#   spu_0008 (136420 B): code ends 0x23210   <- the CRIWARE SPURS task that
#                                               two CreateTask calls await
#           (boot hangs: "[spu_workload] async dispatch MISS fp=0xBCCABE7DDD04E050")
# --merge-chunks is NOT used: it swallows small entry functions (image 6's
# entry at 0xf0), which the registry verifies.
#
# Output: port/spu/<image>/spu_recomp.{c,h} + port/spu/spu_workloads.c
# (auto-registering constructor). CMake picks these up when PORT_SPU_INPUTS is
# empty: file(GLOB port/spu/*/spu_recomp.c).
set -e
here=${0:A:h}
source "$here/env.sh"

SPU="$PES_ROOT/port/spu"
IMG="$PES_ANALYSIS/spu"
KIT="$PS3RECOMP_DIR/tools"

# SPU images whose executable segment embeds a data tail: end of real code.
typeset -A SPU_CODE_END
SPU_CODE_END[spu_0001]=0xb350
SPU_CODE_END[spu_0006]=0x1e258
SPU_CODE_END[spu_0007]=0x22fd0
SPU_CODE_END[spu_0008]=0x23210

mkdir -p "$SPU"
for elf in "$IMG"/spu_*.elf; do
    stem=${elf:t:r}
    ce=${SPU_CODE_END[${stem%%_at_*}]}
    cmd=("$PY" "$KIT/spu_lifter.py" "$elf" --auto-functions "$elf"
         --symbol-prefix "${stem}_" -o "$SPU/$stem"
         --source-name spu_recomp.c --header-name spu_recomp.h)
    [[ -n "$ce" ]] && cmd+=(--code-end "$ce")
    echo "[lift_spu] ${stem}${ce:+ (code-end $ce)}"
    "${cmd[@]}" > /dev/null
done

"$PY" "$KIT/build_spu_workloads.py" --images "$IMG" \
    --lifted "$SPU" --out "$SPU/spu_workloads.c" --constructor --skip-lift
