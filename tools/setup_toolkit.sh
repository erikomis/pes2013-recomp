#!/bin/sh
# Prepare the ps3recomp toolkit this port builds against.
#
#   tools/setup_toolkit.sh            # -> ../ps3recomp-up-r8 (what tools/env.sh expects)
#   tools/setup_toolkit.sh DIR
#
# The port uses Erik's ps3recomp fork at the commit below (the toolkit the
# Deadpool, inFAMOUS and Resistance ports share), plus this repository's toolkit
# changes, all in one patch. A checkout that already has changes of its own is
# never touched.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
dest="${1:-${PS3RECOMP_DIR:-$here/../ps3recomp-up-r8}}"
FORK_URL=https://github.com/erikomis/ps3recomp.git
FORK_BRANCH=deadpool-gameplay
FORK_COMMIT=675ed394
PATCH="$here/patches/ps3recomp-675ed39-pes13.patch"

if [ ! -d "$dest/.git" ]; then
    git clone --branch "$FORK_BRANCH" "$FORK_URL" "$dest"
fi
cd "$dest"
if git apply --reverse --check "$PATCH" 2>/dev/null; then
    echo "toolkit already patched: $dest"
    exit 0
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "$dest has local changes and the patch is not applied: not touching it" >&2
    exit 1
fi
git checkout --quiet "$FORK_COMMIT"
git apply "$PATCH"
echo "toolkit ready: $dest ($FORK_COMMIT + patches/$(basename "$PATCH"))"
