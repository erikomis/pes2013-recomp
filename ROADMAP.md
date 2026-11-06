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
  (3 new shaders in a whole match). To profile next.
- [ ] Confirm in a window, with the final build, on a quiet machine: 60 fps in
  play and clean sound. Other heavy processes on the Mac take it to 15-20 fps.
- [ ] One headless test run ended at about 490 s with no crash report and no
  exit status recorded; the next run went past 590 s. Exit status is now
  recorded by the test scripts. Watch for it in long sessions.

### Game modes

- [ ] Master League and Become a Legend: create, save, load, continue.
- [ ] Saving and loading an edited Option File from inside the game.
- [ ] Online modes: they should fail cleanly offline. Not tested.
- [ ] Trophies (should be a no-op offline). Not tested.

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
- [ ] HD packs: kits, crests, faces and pitch at the sources' resolution (a pack image may be larger than the texture it replaces)
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
- [ ] Positions, abilities, foot, height, age, nationality from eFootball 2026
  cards: record fields decoded, tool written, collection running.
- [ ] Real 2026 faces: 170 PES 2013 PC faces downloaded; showing a PC face on
  PS3 is not proven yet.
- [ ] Kits for the foreign clubs: no 2026 source found.
- [ ] A match, Master League and a Libertadores played through with the profile.
- [ ] Copa do Brasil: the game has no such competition and the Option File has
  no slots for its 126 clubs; only a custom cup with the clubs that exist.
- [ ] Brazilian Portuguese commentary: inventoried, not replaced.

### App to install and play (launcher)

- [x] Tauri app adapted from the Resistance 2 launcher, with inFAMOUS 2 extras.
- [x] Option File profiles (default tree, copies, PS3 save folders, .zip).
- [x] Honest settings: a control whose variable is not in the build says so.
- [ ] First launch of the game from the app, in a window.
- [ ] Release `.dmg`, install and rebuild from the app.

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
