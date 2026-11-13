# Roadmap

🌐 **English** · [Português (BR)](ROADMAP.pt-BR.md)

Status of the native PES 2013 (`BLUS31029`, update 01.04) port to macOS/arm64
and what comes next. `[x]` = done and verified; `[ ]` = to do. The day-to-day
work list, in Portuguese, is [docs/O_QUE_FALTA.md](docs/O_QUE_FALTA.md).

## Status at a glance (2026-11-05)

- **Runs:** boot, logos, title, first-run setup, menus in Portuguese, team
  select, line-ups, anthem and full friendly matches with Data Pack 6 and an
  Option File. A friendly has been played to the end in a window.
- **Speed:** 60.0 fps in gameplay (p95 17.6 ms) and 30.0 fps in replays, at
  about 133% CPU, in a headless match on a quiet Apple-silicon Mac. Before the
  optimisation work it was about 18 fps at 414% CPU.
- **Sound:** the game's mixer runs in real time with no gaps in play; a frame of
  0.1-0.2 s at the start of a replay still drops a few blocks.
- **Next:** that replay-start spike; window modes, internal resolution, image
  filters and texture packs (being ported); the launcher's first real launch;
  a career mode test.
- **Not yet:** Windows and Linux, online.

---

## What is missing to be 100% playable

### Blockers

- [ ] The one-frame spike (112-207 ms) when a replay starts or the scene
  changes, which is where the remaining audio gaps are. Not shader compiles
  (3 new shaders in a whole match). Profiled on 2026-11-06 (`PES_SPIKE_MS`,
  `PS3_FTRACE`): in the windows where audio falls behind, the spike is the title itself busy
  (130-535 ms without asking for a frame) and its audio mixer starved of CPU; not textures,
  shaders or pipelines. Two fixes ready, off until a measurement on an idle machine:
  `PS3_PPU_BOOST_BELOW=700` (higher priority for the title's audio threads) and
  `AUDIO_ELASTIC=12` (64 ms of queue instead of 43). The A/B run with other games open could
  not decide.
- [x] Clicks in the match commentary and crowd (2026-11-08): the mixer sent blocks in bursts
  as CoreAudio freed room, and under match load the title wrote them out of order. Blocks
  now go out on the clock, 5.33 ms apart. Recorded mix of the same match: hundreds of seam
  jumps per 10 s before, 4 in 6 minutes after.
- [ ] Confirm in a window, with the final build, on a quiet machine: 60 fps in
  play and clean sound. Fixed on 2026-11-11, not tried in a window: with the window covered,
  minimized or on another Space, macOS held each frame for up to 1 s (`present` 525-1055 ms in the
  2026-11-08 log) and the sound broke with it; the frame is now drawn and only the present is
  skipped (`PS3_PRESENT_WHEN_HIDDEN=1` brings the wait back). The title's own spike (589 ms at a
  scene change) remains, beyond the audio's 43 ms margin. Other heavy processes on the Mac take it to 15-20 fps.
- [x] One headless test run ended at about 490 s with no crash report and no
  exit status recorded; the next run went past 590 s. Exit status is now
  recorded by the test scripts. On 2026-11-06, 9 headless matches (one of 15 min, the
  others 7-10 min) ended without a crash, only by the requested stop.

### Game modes

- [ ] Master League and Become a Legend: create, save, load, continue.
- [ ] Saving and loading an edited Option File from inside the game.
- [x] Online modes fail cleanly offline (headless, 2026-11-11): Online Community > My
  communities goes back to the menu without a message, no hang. The network dialog answers
  "connected" and the game then sees PSN offline; a "not connected" answer would let it show
  its own message.
- [x] Trophies: the trophy context is created and registered, and the saved data loads, with
  no error. Unlocking one was not tried.

### Window

- [x] Clean exit: closing the window, Cmd-Q or SIGTERM ends the process (after a save in progress); it used to keep running with no window (2026-11-06, SIGTERM tested headless; the close button not yet seen).

### Controls

- [x] Keyboard (Enter = START, Space = CROSS) and DualSense through SDL.
- [ ] Map the full PES control scheme in the launcher and test it in a window.
- [ ] Virtual keyboard: names are accepted automatically (`PS3_OSK_TEXT`); an
  on-screen keyboard is missing.

### Video

- [ ] `.sfd` movies (menu background, intro): play, but decoding is not proven
  for every one.

---

## After it is playable (improvements)

### Graphics and resolution

- [x] Internal resolution 1080p / 1440p / 4K (`PS3_RES_SCALE`), in the build; frame rate per step not measured yet
- [x] HD pitch: the game's two pitches seen in matches at 4096x2048 with grass grain (`gramado-hd`, seen at 2560x1440).
- [x] HD faces: 2026 faces at 512x1024 or 1024x2048 (`faces-2026`, 63 players).
- [ ] HD for the pitches of the other stadiums, the ball, the crowd and ad boards.
- [x] Window modes, window size, screen, vsync (2026-11-05, in the build; not yet seen in a window).
- [x] Picture filters: vibrance, contrast, vignette, grain, colour LUT and presets (unit-tested).
- [x] MetalFX spatial upscaling (unit-tested; not yet seen in a window).
- [x] Texture packs (`PS3_MODS`) and the texture dump (a test pack replaced title-screen textures headless).
- [ ] Ultrawide aspect (wider view, HUD kept 16:9): needs a projection patch for this game.
- [x] Anisotropic filtering 16x by default, FXAA, sharpening.

### Performance

- [x] Optimised build: `-O2` runtime, `-O1` lifted code.
- [x] Quiet log by default (`PS3_VERBOSE=0`).
- [x] Game threads on performance cores (QoS); 59.94 Hz vblank.
- [x] Shadow depth converted on the GPU (no GPU wait per frame).
- [x] Vertex constants staged by range, program memo, buffer pool, bind only
  changed state, whole-range vertex fetch.
- [ ] Replays at 60: the game itself paces them at 30; changing that risks
  running them at double speed. Investigate only after the rest.

### Brazil 2026

- [x] Read the Option File's rosters (players, teams, CRC) and write a test save.
- [x] Collect the 40 Série A/B clubs and the 2026 cup participants with sources.
- [x] Série A and B with 20 clubs each, names in every language, 2026 squads
  for the 40 clubs (2026-11-05, seen headless).
- [x] Libertadores 2026 (38 clubs) and the South American league (18
  Sudamericana clubs) with 2026 squads; crests from Wikimedia.
- [x] 2026 kits 1 and 2 for the 40 clubs, as a texture pack (seen in the team picker).
- [x] No player wears another player's face (14 own faces, the rest fictional).
- [x] Positions, playable positions, abilities, foot, weak foot, form, height,
  age, nationality written for all 2,265 renamed players (2026-11-06; seen in
  Edit > Players). Abilities calibrated to PES 2013's scale.
- [x] Of those, 977 of 2,265 have their eFootball 2026 card (all 89 clubs searched, 2026-11-11); the other
  1,288 have no card on eFootball (mostly Série B) and use a position template.
- [x] Real 2026 faces as a texture pack: 93 players of 17 clubs, at 2-4x the PS3
  resolution. All 93 in Edit (keys recaptured on 2026-11-07 and checked on screen for
  Flamengo); 87 in matches, keyed from 11 automatic friendlies with the bench players starting
  (2026-11-11). Some faces come out with different bytes from run to run; the pack carries
  each variant seen (alias keys).
- [ ] The last 6 faces in matches (Marçal, Allan, Matheus Nascimento, Krovinovic: their match
  texture pairs with no Edit face; Felipe Anderson and Khellven: Palmeiras has no line-up record,
  so they cannot be made to start), and the 23 matched face files with no key and 54 with no 2026 player.
- [x] The stadium creator's 20 stadiums renamed for 2026 (every Série A club
  has its stadium's name); only names, the looks stay.
- [ ] Kits for the foreign clubs: no 2026 source found.
- [ ] New 3D stadiums (Bombonera, Allianz Parque...): would need converting a
  whole stadium model; the game has only Maracanã, Morumbi, Vila Belmiro and
  the Monumental.
- [ ] A match, Master League and a Libertadores played through with the profile.
- [ ] Copa do Brasil: the game has no such competition and the Option File has
  no slots for its 126 clubs; only a custom cup with the clubs that exist.
- [ ] Brazilian Portuguese commentary: inventoried, not replaced.

### App to install and play (launcher)

- [x] Tauri app adapted from the Resistance 2 launcher, with inFAMOUS 2 extras.
- [x] Option File profiles (default tree, copies, PS3 save folders, .zip).
- [x] Honest settings: a control whose variable is not in the build says so.
- [x] First launch of the game from the app, in a window (sessions from 2026-11-06 to 11-08 in the launcher logs).
- [ ] Release `.dmg`, install and rebuild from the app.
- [ ] RecompLauncher: the profile (`recomplauncher.json`), the launcher's
  headless `--prepare` / `--play` and `scripts/package-recomplauncher.sh` are
  in, and release v0.1.0 carries that zip; a full prepare on a clean Mac and the
  listing on recomplauncher.com are still to do (launcher README,
  "RecompLauncher").

### Other platforms

- [ ] Windows and Linux.

---

## Done and finished

### Boot and pipeline

- [x] Disc and update inventoried; 01.04 decrypted (NPDRM rev 0x19, free licence).
- [x] 23,462 PPU functions lifted; 9 SPU images and 2 SPURS jobs lifted.
- [x] `stop 0x110` (SPU receive event): the black screen at boot.
- [x] `PS3_HDD1_ROOT` for the system cache: the stuck loading screen.
- [x] Nested guest callbacks on their own stack: the exit after the title.
- [x] On-screen keyboard events: the stuck difficulty page.
- [x] Unlifted SPURS job loaded where the kernel does not clear it.

### Graphics

- [x] Far players and referee (surface table, main-memory write-back).
- [x] Fragment programs complete (NV308A inline upload).
- [x] Kits not striped (mip pitch).
- [x] Animation (SPURS `JOBLIST`).
- [x] Random match freeze (FIFO ring recycle needs 250 ms without progress).

### Toolkit

All of the above live in the shared toolkit and help the other ports too. They
are carried in `patches/` and applied by `tools/setup_toolkit.sh`.
