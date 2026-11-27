# Windows (x64)

🌐 **English** · [Português (BR)](WINDOWS.pt-BR.md)

The port builds on Windows 10/11 x64 with clang-cl and the toolkit's **Vulkan**
backend, which runs the same register-file draw engine the Metal build uses.
Everything Windows-specific lives in `tools/windows/` and in
`patches/ps3recomp-e85647a-pes13-windows.patch`; the macOS build is unchanged.

> [!WARNING]
> **Experimental.** PES 2013 reaches the menus and plays the training ground
> at 60 fps on Windows. A full match, a long session and controllers have not
> been checked yet.

## What you need

- Windows 10 or 11, x64, a CPU with AVX2 (any from about 2015 on), a GPU with a
  Vulkan driver, about 25 GB free on the drive that holds the repository.
- Your own copy of PES 2013: the US disc image (`BLUS31029`) as an `.iso` (or a
  folder dump that holds `PS3_GAME`), the 01.04 update and, if you want them,
  Data Pack 6 and an Option File. As on macOS: nothing of the game is in this
  repository.
- The key file for `tools/decrypt_self.py` (see the top of that script).

## Building

```powershell
# once: Git, CMake, Ninja, Python 3.12, LLVM, VS 2022 Build Tools (C++),
# vcpkg with sdl2[vulkan], glslang and vulkan-headers, and the .venv
powershell -ExecutionPolicy Bypass -File tools\windows\install_deps.ps1

# the toolkit, in ..\ps3recomp-pes-win
powershell -ExecutionPolicy Bypass -File tools\windows\setup_toolkit.ps1

# your files
#   game\EBOOT.BIN, PARAM.SFO, ICON0.PNG, PS3LOGO.DAT  <- the 01.04 update
#   game_iso\<the disc>.iso                            <- or set PES_ISO / PES_DISC_DIR
#   tools\self_keys.txt                                <- or %APPDATA%\pes13-recomp\keys\self_keys.txt
#   BLUS31029_DOWNLOAD\USRDIR, PARAM.SFO               <- Data Pack 6, optional

# decrypt, analyse, lift (PPU, SPU, SPURS jobs), build
powershell -ExecutionPolicy Bypass -File tools\windows\rebuild.ps1
```

One way to get the 01.04 files: install the update PKG in RPCS3 and copy them
from `dev_hdd0\game\BLUS31029\` (EBOOT.BIN from its `USRDIR`).

`rebuild.ps1` takes the steps as arguments (`decrypt analyse lift spu build`),
like `tools/rebuild.sh`. `build.ps1` alone rebuilds after a change;
`-Reconfigure` runs CMake again, `-Jobs N` sets the parallel compiles (default:
one per 6 GB of RAM). Each lifted chunk is tens of MB of C++, and the build
stops itself if free memory falls under 10%.

Option File: `tools\install_savedata.py SAVEDATA rpcs3\dev_hdd0\home\00000001\savedata --keys <file>`
with the `.venv` Python, as on macOS.

## Playing

```powershell
powershell -ExecutionPolicy Bypass -File tools\windows\run.ps1
```

`run.ps1` mounts the disc image read-only (no administrator rights needed),
assembles the game's file tree under `rpcs3\dev_hdd0\disc\BLUS31029` with
directory junctions, and starts the game. Its output goes to
`cache\boot-last.log` (`PES_LOG=-` keeps it on the console). Settings go after
it as `VAR=value`, like `tools/run.sh`:

| Setting | What it does |
| --- | --- |
| `PS3_LANG=PT` | Console language (default `PT`), as on macOS |
| `PS3RECOMP_VK_FULLSCREEN=1` | Full screen |
| `PS3RECOMP_VK_DEVICE=<n>` | Which GPU, when there is more than one |
| `PS3RECOMP_VK_FPS=1`, `RSX_PACE_LOG=5` | Frame rate; frame pacing every 5 s |
| `PS3_RES_SCALE=1080p\|1440p\|4k` (or `1`..`4`) | Internal resolution: every render target that many times the PS3's 720p, supersampled to the window (default `1`) |
| `PS3_ANISO=16` | Anisotropic filtering where the game uses mipmaps (default `16`; `0` = the game's own) |
| `PS3_AA=smaa` | SMAA 1x on the frame, at the internal resolution |
| `PS3_SHARPEN=0..1`, `PS3_VIBRANCE=-1..1`, `PS3_CONTRAST=0.5..1.5` | AMD CAS sharpening, vibrance, contrast (one pass) |
| `PS3_VSYNC=1` | Wait for the display (FIFO); default is MAILBOX, which never blocks and does not tear |
| `VK_DRAW_BATCH=0` | One submit and wait per draw, as before (default `1`; without it, about half the frame rate) |
| `VK_DRAW_BATCH_ASYNC=0`, `PES_SPLIT_PRESENT=0` | Batches and presents that wait for the GPU, as before |
| `PES_EVENTS=0`, `PS3_PAD_SPEAKER=0`, `PS3_PAD_LIGHT=#rrggbb` | The DualSense match effects, as on macOS |
| `PS3_VERBOSE=1` | The full runtime log (very large) |

Controllers: DualSense, DualShock 4, Xbox and the other pads SDL knows, with
rumble (the toolkit is built with `PS3RECOMP_PAD_SDL2`). Without a controller
the keyboard is pad 1: arrows the d-pad, Z/X/A/S cross/circle/square/triangle,
Q/W L1/R1, 1/2 L2/R2, Enter START, Tab SELECT.
Closing the window ends the game, after a save in progress finishes.

## How it differs from the macOS build

- **Toolkit.** macOS builds against erikomis/ps3recomp `675ed394` plus
  `patches/ps3recomp-675ed39-pes13.patch`. Windows builds against
  sp00nznet/ps3recomp master `e85647a3`, which already has the Vulkan backend on
  Windows, clang-cl builds, x86 SSE4.1/AVX2 SPU helpers and WASAPI audio, with
  this port's toolkit changes merged onto it (`patches/ps3recomp-e85647a-pes13-windows.patch`).
  Most of them were already upstream; the rest came across: semaphore ids with
  a generation (the Master League hang), the write-back of small main-memory
  targets (the far players' kits), main-memory GPU reports at IO `0x0E000000`,
  the FIFO overrun that must persist before it is recycled, GETLLAR polls that
  park instead of spinning, the DualSense match effects, the save-busy count the
  quit path waits on, and the rest of the macOS patch where it is not Metal.
- **Metal-only features are not there yet:** MetalFX, FXAA, the colour LUT
  and grain, texture packs
  (`PS3_MODS`: the HD pitch, the 2026 faces and kits), the native on-screen
  keyboard prompt and the audio device choice. The Vulkan backend would need
  each of them.
- **The launcher** (`launcher/`) is macOS-only for now.

## What has been checked (2026-11-27, Ryzen 5 5600, RTX 4070 Ti SUPER)

- `setup_toolkit.ps1` from a fresh clone gives exactly the tree the build was
  made with (same git tree hash).
- The toolkit runtime and the port's runner, scaffold and overrides build with
  clang-cl 23 and link with lld-link; the port's definitions of the lifted
  functions it replaces win over the weak lifted ones (checked in the link map).
- The toolkit's synthetic boot title (`tools/make_smoke_elf.py`) passes through
  `PES2013Recomp.exe`: loader, NID bridge, guest threads, FIFO, flips and vblank,
  on the Vulkan backend both offscreen and in a Win32 window, through `run.ps1`
  (ISO mounted, junctions made, PARAM.SFO read through them).
- `ppu_loader.py` and `ppu_lifter.py` run on Windows on a real 10 MB EBOOT
  (another title's): 14 files, 1.7 GB, 4 minutes; `weaken_lifted.py` reads them.

- The recompiled PES 2013 opens from the BLUS31029 disc and 1.04 update, saves
  the first-run settings and reaches the main menu. The toolkit patch makes the
  Windows EDAT cache accept absolute paths so `dt10.sdat` loads correctly.
- The Windows mixer now schedules each guest audio period on a steady clock and
  applies the launcher’s PPU priority threshold. In 30 seconds after startup,
  the share of silent blocks in the menu fell from about 85% to 0.3%, with
  no dropped frames reported by WASAPI in either capture.
- The Vulkan draw path synchronizes texture uploads and render targets before
  shaders sample them, including when draw batching is disabled.
- Draw batching (`VK_DRAW_BATCH=1`, now the default in `run.ps1`): in the
  training ground the frame rate went from about 30 fps (p95 80-95 ms, the FIFO
  drain taking 30-90 ms a frame with one submit and wait per draw) to 59.9 fps
  (p50 16.6 ms, p95 20 ms), same picture. Audio in the same runs: 187.5
  blocks/s, 0% silent, no underruns.
- Internal resolution (`PS3_RES_SCALE`): matches at 1440p and 4K internal
  render correctly (players, kits, stands, crowd, shadows, HUD, replays with
  depth of field) on a 1920x1080 screen, at 60 fps (4K: p50 16.7 ms, p95
  18.7-23 ms, GPU about 40%). That took two changes to the Vulkan presenter:
  draw batches in two slots, so a flush no longer waits for the GPU (it held
  the FIFO thread for the frame's whole GPU time: 30 fps at 1440p), and a
  MAILBOX swapchain instead of FIFO (each acquire waited for a vblank).
- SMAA and CAS (`PS3_AA=smaa PS3_SHARPEN=0.3`), drawn with the engine
  backend's own pipelines: 57-60 fps at 1x and at 4K internal, edges smoothed,
  no artefacts in matches.

## Temporal upscalers (DLSS, FSR 3/4) and frame generation

Not here, and not a switch away. DLSS (any version), FSR 3.1 and FSR 4 are
temporal: they need per-pixel motion vectors, the frame's depth and a sub-pixel
jitter in the game's projection, none of which the PS3's frame has. The God of
War: Ascension port (rigaz29/Ascension-R) has DLSS and FSR 4.1 because it
reverse-engineered that game's renderer: its camera matrices, its motion-blur
velocity buffer, where the HUD starts. PES 2013 would need the same study of its
own renderer. FSR 4's model also runs on AMD Radeon only (on NVIDIA the FSR SDK
falls back to FSR 3.1), and DLSS 5 was announced for RTX 50 cards. Rendering at
4K internal resolution and reducing it to the screen gives most of what an
upscaler would here.
