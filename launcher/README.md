# Launcher (Tauri)

A desktop app for the PES 2013 port (Pro Evolution Soccer 2013, US disc
BLUS31029 with the 01.04 update) on Apple-silicon macOS: it plays the game the
way `tools/run.sh` does, keeps the settings, manages Option File profiles and
saves, shows the controls, the log and the build's state, and rebuilds the port
with `tools/rebuild.sh`. It ships no game code or files: the cover art on Home
comes from the player's mounted disc (`PS3_GAME/ICON0.PNG`, `PIC1.PNG`), and the
app icon is a plain football drawn by `scripts/make_icon.py`.

It is the Resistance 2 port's launcher adapted to this game, with the
inFAMOUS 2 launcher's extra picture controls (aspect, tone curve, clarity,
colour presets) and trophy list. The UI is in Brazilian Portuguese by default,
with English in the sidebar.

## Building

```sh
cd launcher
npm ci
npx tsc --noEmit                      # the frontend's types
(cd src-tauri && cargo test -j 2)     # the backend's tests
npm run release                       # stage the port's sources, build the .app and the .dmg, check both
```

`npm run release` is `scripts/stage_port.py` (the port's sources into
`launcher/stage/port`, ignored by git), `tauri build --config
src-tauri/tauri.bundle.conf.json` (bundles that folder as `Resources/port`,
targets app and dmg) and `scripts/check_bundle.py` on both results.

On this machine, build only when no `PES2013Recomp` is running and with
`nice` (the repository's `AGENTS.md`). `node_modules`, `dist` and
`src-tauri/target` are ignored.

## Install the game

The repository is private, so the app carries the port's own sources instead of
cloning them: `scripts/stage_port.py` copies `LICENSE`, `CREDITS*.md`, the four
files of `port/`, `patches/ps3recomp-675ed39-pes13.patch` and the tools an
install and Play run (`env.sh`, `run.sh`, `rebuild.sh`, `build.sh`,
`lift_spu.sh`, `lift_jobs.sh`, `setup_toolkit.sh`, `decrypt_self.py`,
`install_savedata.py`, `pes2013_edit.py`), with a `BUILD_INFO.json` naming the
commit. Nothing lifted, no game file and no key.

Home shows the **Install the game** card while nothing is built. The player
chooses:

- the US disc image (`.iso`, BLUS31029),
- the 01.04 update (`.pkg`; its header's content id must name BLUS31029),
- a key file in `self_keys.txt` format (NPDRM keys up to revision 0x19 and
  `NP_klic_free`); nothing ships with the app, and the launcher only checks that
  the file exists and hands its path to `tools/decrypt_self.py`,
- optionally the Data Pack 6 folder (linked) or `.pkg` (extracted), and an
  Option File folder with its `savedata_keys.txt`.

Then `src-tauri/src/install.zsh` runs in `~/Library/Application Support/pes13-recomp/`
(its own process group, under `nice`, Cancel stops the group), each step
announced as `==> <step>` for the progress bar, its output also in
`install.log`:

1. **prerequisites** (before the script): Apple's Command Line Tools (their
   installer, waited for) and `cmake ninja sdl2 python@3.12` from Homebrew,
   installed only after the player says yes to the `brew install` line shown;
2. **sources**: the bundled stage into `port/` (rsync, never deleting what earlier
   runs made);
3. **toolkit**: `port/tools/setup_toolkit.sh toolkit/` clones the public
   `erikomis/ps3recomp` branch `deadpool-gameplay`, checks out 675ed394 and
   applies the patch (already patched: left alone);
4. **venv**: `venv/` from Python 3.12 with the toolkit's `requirements.txt` and
   `pycryptodome` (kept once complete);
5. **game**: the toolkit's `tools/pkg_extract.py` extracts the update into
   `port/game/` (EBOOT.BIN, PARAM.SFO, ICON0.PNG, PS3LOGO.DAT), checking its
   PARAM.SFO says BLUS31029 01.04; `port/game_iso/BLUS31029.iso` becomes a link
   to the image; the data pack is linked or extracted to
   `port/BLUS31029_DOWNLOAD`;
6. **decrypt, analyse, lift, spu, build**: `port/tools/rebuild.sh <step>` with
   `PS3RECOMP_DIR`, `PES_VENV` and `PES_KEYS` pointing at the folders above; a
   step that succeeded is skipped on the next run until `game/EBOOT.elf`
   changes, and the build is incremental;
7. **optionfile**: `tools/install_savedata.py` into a new profile, `Option File`
   (never into an existing one).

When it ends well, Play uses `port/` (the port folder setting) and the Option
File profile becomes the active one. A developer keeps using a checkout:
Advanced > Install / rebuild > the port folder.

## What Play does

```sh
cd <port> && [caffeinate -i] /bin/zsh tools/run.sh  > <data>/last.log.raw 2>&1
```

with the settings in the environment. `tools/run.sh` assembles the VFS tree,
mounts the disc image behind `game_iso` read-only at `~/mnt_pes13` when it is
not mounted yet, sets its defaults with `${VAR:-default}` (so what the launcher
sets wins) and ends in `exec`, so the game keeps the pid Play started; the game
opens its own Metal window. A thread copies the output into `<data>/last.log`
with the seconds since launch before each line; the previous log moves to
`<data>/logs/` (10 kept).

- **Stop** sends SIGTERM to that process group, and SIGKILL 8 s later if it is
  still there. Only that group, by its pid: nothing is ever stopped by name.
- Play is refused while another `PES2013Recomp` runs (a terminal, another
  session), while a rebuild runs and while an Option File profile is being
  changed.
- With the default settings the environment is run.sh's own plus `PES_ROOT`
  and the active profile's `PS3_GAMEDATA_ROOT` (a test checks this).
- `<data>` is `~/Library/Application Support/pes13-recomp/`. Its `keys/`
  folder is the owner's: the launcher only checks that
  `keys/savedata_keys.txt` exists and hands that path to
  `tools/install_savedata.py`. It never reads, copies, lists, backs up or zips
  it (tests check backups, zips and profile copies).

## Controls that the build does not have yet

Every variable a control drives is searched for in
`build/BLUS31029/PES2013Recomp` (a NUL-terminated name; `FEATURE_MARKERS` in
`src-tauri/src/lib.rs`, cached by size and time in `<data>/build-features.json`).
A control whose variable is missing is greyed out with "Not available in this
build (NAME is not in the executable)", and Play does not pass that variable.

Checked against the executable of 5 November 2026, the build reads:
`PS3_LANG`, `PS3_AA` (FXAA only), `PS3_SHARPEN`, `PS3_ANISO`,
`PS3_DISPLAY_GAMMA`, `PS3_INPUT_MAP`, `PS3_INPUT_MODE`, the `PS3_MOUSE*`
variables, `PS3_RUMBLE`, `PS3_RUMBLE_STRENGTH`, `PS3_PAD_LOG`,
`PS3RECOMP_METAL_FPS`, `PS3_VERBOSE`, `PS3_NO_AUDIO`, and the port's
`PS3_FRAMECLOCK_US`, `PS3_VBLANK_US`, `PS3_QOS`, `GCM_PUT_DOORBELL`,
`RSX_PACE_LOG`, `AUDIO_ELASTIC`.

Unavailable for now (the controls are there and say so): window mode, size and
screen, vsync, MetalFX, internal resolution, aspect, SMAA, vibrance, contrast,
clarity, the tone curve, vignette, grain, the LUT file, presets and strength,
volume and output device, texture packs and the texture dump, the vertex-cache
and bind switches, `PS3_SHADER_CACHE` and the background shader builds,
telemetry, slow-FIFO-pass and cache-statistics logging, and the FFmpeg movie
switches (`PS3RECOMP_FFMPEG*`: the build is not configured with
`PS3RECOMP_FFMPEG_RUNTIME`).

**Mute.** The runtime's `PS3_MUTE` (silence at the device) is only in its
Windows audio backend. The macOS build has `PS3_NO_AUDIO`, which tells the game
that audio is unavailable, so the game takes its silent path. Mute uses the
best of `PS3_AUDIO_MUTE`, `PS3_MUTE`, `PS3_NO_AUDIO` the build has, and says
which one in its hint.

## Pages

- **Home / Início**: the disc art when mounted, "BLUS31029 · version 01.04",
  **Play** / Stop, a bar for whatever blocks Play (no build, no disc and no
  image in `game_iso`, a disc that is not BLUS31029, a missing profile), a
  note when `BLUS31029_DOWNLOAD/` (the data pack) is missing, quick settings,
  the active Option File and the newest save, the status (state, disc, data
  pack, port folder) with the log, Updates, a Play shortcut on the Desktop and
  Add to Steam.
- **Graphics / Gráficos**: window, image quality (profile, internal resolution,
  aspect, MetalFX, anti-aliasing, sharpening, anisotropic filtering, 16× by
  default as in run.sh, gamma override), filters (vibrance, contrast, clarity,
  shadows, midtones, highlights, vignette, grain, LUT file, colour preset, LUT
  strength) and texture packs, each marked when the build lacks it.
- **Performance / Desempenho**: the frame clock (`PS3_FRAMECLOCK_US`, 1 ms),
  vblank (`PS3_VBLANK_US`, 59.94 Hz), user-interactive threads (`PS3_QOS`),
  the PUT doorbell (`GCM_PUT_DOORBELL`), the fps counter, keep the Mac awake;
  the vertex cache and bind switches; the translated shaders on disk
  (`RSX_MSL_CACHE`, run.sh's `cache/msl`: size and **Clear**) and the shader
  switches.
- **Game / Jogo**: the disc (the image in `game_iso` and where run.sh mounts it,
  **Mount the game_iso image now**, another image or a folder, eject, mount on
  Play), the data pack, the console language (empty = run.sh's `PT`), movies,
  audio (mute, the longer audio queue `AUDIO_ELASTIC`, on as in run.sh,
  volume and device), the trophies (names and icons from the disc's
  `TROPHY.TRP`, unlocks from the active profile's `trophies/`), the saves
  manager and its backups.
- **Option File**: below.
- **Controls / Controles**: the bindings table (keyboard, mouse buttons,
  controller) written to `<data>/input.toml` and passed as `PS3_INPUT_MAP`
  (format: the toolkit's `libs/input/pad_input_map.h`; no file = the runtime's
  built-in layout, Restore defaults moves the file to `input.toml.bak`), what
  each PS3 control does in PES 2013's default layout, the controller test,
  what drives the game (`PS3_INPUT_MODE`), the mouse (it moves the right
  stick) and vibration with a test pulse.
- **Advanced / Avançado**: Install / rebuild (what the Mac has, the port folder,
  `tools/rebuild.sh` with the chosen steps under `nice`, its `build` step going
  through `tools/build.sh` and its guards; JOBS sets the lifter only), Updates,
  the game log, debug mode, extra variables and the equivalent command line.

### The control labels

Where they come from: segmentnext.com's "PES 2013 Controls Guide" (Xbox names),
psxdatacenter.com's page for this game's PS2 version (SLUS-21955), and this
port's own drill ("Pulsa R2 al regatear"). ✕ short pass / tackle, ○ long pass,
lob / sliding tackle, □ shoot / pressure, △ through ball / keeper out, R1
sprint, L1 switch player, R2 special skills and dribbling, L2 finesse shot /
directed pass, R3 flick when trapping, START pause, D-pad move / menus, left
stick move and dribble, right stick tricks. L3 and SELECT show no function: no
source was found for them. The keyboard defaults are the runtime's, written
for a shooter.

## Option File profiles

A profile is a `PS3_GAMEDATA_ROOT`: a folder with
`dev_hdd0/home/00000001/savedata` (and the runtime's `trophies/`). Play passes
the active one.

- **padrão** is built in: `<port>/rpcs3`, run.sh's default, with the owner's
  Option File. It is never deleted and never installed into.
- **Made here** profiles live in `<data>/profiles/<name>/`. Create one empty,
  as a copy of another (saves and trophies only, not padrão's VFS tree), from a
  folder of PS3 saves, or from a .zip. Each is built in a hidden
  `.<name>.partial` and renamed when complete.
- **From a folder of PS3 saves** runs
  `tools/install_savedata.py SRC <new profile> --keys <data>/keys/savedata_keys.txt`
  with the tools' venv Python (`../deadpool-recomp/tools/.venv`, or
  `PES_VENV`), streamed into the page, cancellable, its own process group.
  `SRC` may be the folder with the saves, or one holding `PS3/SAVEDATA` or
  `SAVEDATA`; saves whose PARAM.PFD is not a console's (already decrypted) are
  refused with a pointer to the other options.
- **Registered folders** (for example a test save) are used where they are,
  without copying. The launcher only reads them: importing, restoring and
  deleting are off there, and removing one from the list leaves the folder
  alone. The game itself writes there while it plays with it.
- Each profile lists its save count and size, whether `BLUS31029EEDIT` is
  there, and its team and player counts from `tools/pes2013_edit.py` (read-only,
  under `nice`, once per file version; about 0.25 s on the real Option File:
  417 teams, 8993 players).
- Export / import a .zip per profile (import only into a profile made here).
  The archive limits fit a full Option File (about 1100 saves, 4400 files,
  250 MB): at most 16384 entries, 64 MB a file, 1 GB in all.
- Names are sanitised (letters of any alphabet, digits, space, `-`, `_`; at most
  64; "padrão" reserved; case-insensitive duplicates refused). Registered
  paths must be absolute, without `..`, and not inside the launcher's own
  folder. A local profile is deleted only after confirmation and only when it
  is a real folder directly under `profiles/`.
- Switching profiles and every change are refused while the game runs.

## Saves manager

The active profile's saves and, read-only, RPCS3's (the repository's rules:
nothing writes into RPCS3's saves; a slot can be copied from RPCS3 into the
profile, never the other way). Numbered saves (faces, kits, stadium parts)
collapse by family; hashes are computed only for slots present on both sides.
Every replace or delete is backed up first, per profile, in
`<data>/save-backups/<profile>/`. The automatic backup before Play is off by
default here (0 kept): it would copy about 250 MB each time. Backups on request
remain.

## Updates

The port folder is not a git checkout and the port has no release page, so the
Updates tab says so and the app makes no network request. `update.rs` keeps the
git flow (fetch, behind, `git pull --ff-only`) for a checkout and a GitHub
release check for when `REPO` is set.

## Left out, and why

- The build-tools bootstrap of other ports (Homebrew is used instead) and the
  RPCS3 decrypt fallback: this port decrypts with `tools/decrypt_self.py` and the
  player's key file.
- The play-folder setting and the first-boot HDD install: saves are profiles,
  and this title reads its data from the disc.
- Resistance 2's draw-engine switches (`PS3RECOMP_ENG_ZETA16_GPU`,
  `_FETCH_MANY`, `_VCACHE_SPARSE`, `_VCACHE_FRAMEREUSE`, `_VCACHE_CHURN`,
  `_BLIT_GPU`, `_GUEST_WRITE`, `PS3RECOMP_FP_UNNORM_VOL`): fixes for that
  game's engine; they can still be passed as extra variables.
- inFAMOUS 2's signed self-update (it needs a release repository and a signing
  key), its voice/text languages and button-icon switch (that game's patches).
- Windows: the game is macOS only.

## Debug mode

As in the Resistance 2 launcher: a session folder with the log, the whole frame
every 120 presents (`PS3RECOMP_METAL_FRAME_DUMP`), failed syscalls
(`LV2_ERRDBG`), the verbose log, Capture this frame, Analyse and a .zip. The
pass-by-pass capture on request needs `RSX_ENGINE_PASS_DUMP_TRIGGER`, which this
runtime does not have; without it `RSX_ENGINE_PASS_DUMP` is not passed (it would
dump from the first frame) and a capture keeps the whole frame only.

## Screens without the game

`scripts/ui-mock.js` is a fake backend for the built page (`npm run build`, then
serve `dist/` with the script loaded first; `scripts/screenshots.sh` does this
with a headless Chrome). `?allFeatures=1` shows a build with every variable.
