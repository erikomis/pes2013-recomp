#!/bin/zsh
# "Install the game": from the player's own files to a build Play can run. The
# launcher runs this (src-tauri/src/lib.rs, start_install) in its data folder, in
# its own process group, and reads the "==> <step>" lines for its progress bar.
# Each step skips what an earlier run already finished, so pressing Install again
# after a failure or a Cancel continues where it stopped.
#
# Inputs, all from the environment:
#   PES_DATA        the launcher's data folder (~/Library/Application Support/pes13-recomp)
#   PES_STAGE       the port's sources bundled in the app (Resources/port)
#   PES_ISO         the US disc image (BLUS31029), linked as port/game_iso/BLUS31029.iso
#   PES_PKG         the 01.04 update .pkg
#   PES_KEYS        the player's key file (self_keys.txt format); only handed to
#                   tools/decrypt_self.py, never copied or printed
#   PES_PACK        optional: the Data Pack 6 folder (linked) or .pkg (extracted)
#   PES_OPTIONFILE  optional: a folder of PS3 saves, installed as the profile
#   PES_SAVEKEYS    "Option File" by tools/install_savedata.py with this key file
#   PES_STEPS       the steps to run (default: all, in order)
#   JOBS            the lifter's parallel jobs (the compile stays at tools/build.sh's 2)
#
# Steps: sources toolkit venv game decrypt analyse lift spu build optionfile
#
# What it makes, all inside PES_DATA:
#   port/      the port (PES_ROOT for tools/*.sh): the sources, game/, game_iso/,
#              BLUS31029_DOWNLOAD (a link or the extracted pack), and what
#              tools/rebuild.sh writes (analysis/, recompiled/, port/spu, build/)
#   toolkit/   ps3recomp at 675ed394 + patches/ps3recomp-675ed39-pes13.patch
#   venv/      Python 3.12 with the toolkit's requirements.txt and pycryptodome
#   profiles/Option File/   when PES_OPTIONFILE is given
set -e
setopt null_glob
: ${PES_DATA:?} ${PES_STAGE:?}
PORT=$PES_DATA/port
TK=$PES_DATA/toolkit
VENV=$PES_DATA/venv
PY=$VENV/bin/python
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export PES_ROOT=$PORT PS3RECOMP_DIR=$TK PES_VENV=$VENV PY
[ -n "$PES_KEYS" ] && export PES_KEYS
steps=(${=PES_STEPS:-sources toolkit venv game decrypt analyse lift spu build optionfile})
want() { (( ${steps[(Ie)$1]} )); }
say() { echo "==> $1"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
# a step that rebuild.sh runs, skipped when its stamp is newer than game/EBOOT.elf
done_since_elf() { [ -f "$PORT/cache/install.$1" ] && [ "$PORT/cache/install.$1" -nt "$PORT/game/EBOOT.elf" ]; }
mark() { mkdir -p "$PORT/cache"; touch "$PORT/cache/install.$1"; }

if want sources; then
    say sources
    [ -f "$PES_STAGE/tools/rebuild.sh" ] || fail "the app carries no port sources ($PES_STAGE)"
    mkdir -p "$PORT"
    # the sources only: what earlier runs made (game/, build/, ...) stays
    /usr/bin/rsync -a "$PES_STAGE"/ "$PORT"/
    chmod 755 "$PORT"/tools/*.sh "$PORT"/tools/*.py
    echo "  $(cat "$PORT/BUILD_INFO.json" | tr -d '\n ' | cut -c1-120)"
fi

if want toolkit; then
    say toolkit
    /bin/sh "$PORT/tools/setup_toolkit.sh" "$TK"
fi

if want venv; then
    say venv
    if [ ! -f "$VENV/.pes-ready" ]; then
        py312=$(command -v python3.12 || true)
        [ -n "$py312" ] || fail "Python 3.12 is missing (brew install python@3.12)"
        rm -rf "$VENV"
        "$py312" -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --disable-pip-version-check -r "$TK/requirements.txt" pycryptodome \
            || fail "could not install the Python packages (they come from the internet)"
        touch "$VENV/.pes-ready"
    fi
    "$PY" -c "import Crypto, capstone" || fail "the Python environment is incomplete: $VENV"
fi

if want game; then
    say game
    G=$PORT/game
    mkdir -p "$G"
    if [ ! -f "$G/EBOOT.BIN" ] || [ -n "$PES_PKG" -a "$PES_PKG" -nt "$G/EBOOT.BIN" ]; then
        [ -f "$PES_PKG" ] || fail "the 01.04 update .pkg was not given or is not there"
        tmp=$PORT/cache/pkg.partial
        rm -rf "$tmp"; mkdir -p "$tmp"
        "$PY" -I "$TK/tools/pkg_extract.py" "$PES_PKG" "$tmp" || fail "could not extract the update .pkg"
        [ -f "$tmp/USRDIR/EBOOT.BIN" ] || fail "that .pkg has no USRDIR/EBOOT.BIN: it is not the game's update"
        "$PY" -I - "$tmp/PARAM.SFO" <<'PYEOF' || fail "that .pkg is not the BLUS31029 01.04 update"
import struct, sys
d = open(sys.argv[1], 'rb').read()
kt, dt, n = struct.unpack('<III', d[8:20])
v = {}
for i in range(n):
    ko, fmt, ln, mx, off = struct.unpack('<HHIII', d[20 + 16 * i:36 + 16 * i])
    k = d[kt + ko:d.index(b'\0', kt + ko)].decode()
    v[k] = d[dt + off:dt + off + ln].rstrip(b'\0').decode('utf-8', 'replace') if fmt != 0x404 else ''
print('  update:', v.get('TITLE_ID'), v.get('APP_VER'), v.get('TITLE'))
sys.exit(0 if v.get('TITLE_ID') == 'BLUS31029' and v.get('APP_VER') == '01.04' else 1)
PYEOF
        for f in PARAM.SFO ICON0.PNG PS3LOGO.DAT; do [ -f "$tmp/$f" ] && cp "$tmp/$f" "$G/$f"; done
        # a new EBOOT.BIN: the decrypted one and everything made from it are stale
        rm -f "$G/EBOOT.elf"
        mv "$tmp/USRDIR/EBOOT.BIN" "$G/EBOOT.BIN"
        rm -rf "$tmp"
    fi
    echo "  game/EBOOT.BIN: $(shasum -a 256 "$G/EBOOT.BIN" | cut -c1-16)"
    if [ -n "$PES_ISO" ]; then
        [ -f "$PES_ISO" ] || fail "the disc image is not there: $PES_ISO"
        mkdir -p "$PORT/game_iso"
        # tools/run.sh mounts the first *.iso here, read-only; only links are replaced
        for l in "$PORT"/game_iso/*.iso; do [ -L "$l" ] && rm -f "$l"; done
        ln -s "$PES_ISO" "$PORT/game_iso/BLUS31029.iso"
        echo "  game_iso -> $PES_ISO"
    fi
    if [ -n "$PES_PACK" ]; then
        P=$PORT/BLUS31029_DOWNLOAD
        if [ -d "$PES_PACK" ]; then
            [ -d "$PES_PACK/USRDIR" ] || fail "the data pack folder has no USRDIR: $PES_PACK"
            [ -L "$P" -o ! -e "$P" ] || fail "$P is already a folder: remove it to link another pack"
            ln -sfn "$PES_PACK" "$P"
            echo "  data pack -> $PES_PACK"
        elif [ ! -d "$P/USRDIR" ] || [ "$PES_PACK" -nt "$P/USRDIR" ]; then
            tmp=$PORT/cache/pack.partial
            rm -rf "$tmp"; mkdir -p "$tmp"
            "$PY" -I "$TK/tools/pkg_extract.py" "$PES_PACK" "$tmp" || fail "could not extract the data pack .pkg"
            [ -d "$tmp/USRDIR" ] || fail "that .pkg has no USRDIR: it is not a data pack"
            [ -L "$P" ] && rm -f "$P"
            rm -rf "$P"; mv "$tmp" "$P"
            echo "  data pack extracted into $P"
        fi
    fi
fi

for s in decrypt analyse lift spu build; do
    want $s || continue
    if [ $s != decrypt ] && [ $s != build ] && done_since_elf $s; then
        say $s; echo "  done by an earlier run"; continue
    fi
    # rebuild.sh prints its own "==> <step>"
    "$PORT/tools/rebuild.sh" $s
    [ $s = decrypt ] || mark $s
done

if want optionfile && [ -n "$PES_OPTIONFILE" ]; then
    say optionfile
    name="Option File"
    dst=$PES_DATA/profiles/$name
    if [ -e "$dst" ]; then
        echo "  the profile \"$name\" already exists: left as it is"
    else
        [ -f "$PES_SAVEKEYS" ] || fail "the Option File needs its key file (savedata_keys.txt)"
        stage=$PES_DATA/profiles/.$name.partial
        rm -rf "$stage"; mkdir -p "$stage/dev_hdd0/home/00000001/savedata"
        "$PY" -I "$PORT/tools/install_savedata.py" "$PES_OPTIONFILE" "$stage/dev_hdd0/home/00000001/savedata" \
            --keys "$PES_SAVEKEYS" || { rm -rf "$stage"; fail "could not install the Option File"; }
        mv "$stage" "$dst"
    fi
fi
say done
