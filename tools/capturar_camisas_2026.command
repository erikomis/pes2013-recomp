#!/bin/zsh
set -eu
export PES_ROOT=${0:A:h:h}
source "$PES_ROOT/tools/env.sh"
exec "$PY" "$PES_ROOT/tools/capture_kit_textures.py" "$@"
