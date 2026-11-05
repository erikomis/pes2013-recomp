# Credits

🌐 **English** · [Português (BR)](CREDITS.pt-BR.md)

This port only exists because of the work below. Thank you all.

## Toolkit and base

- **[ps3recomp](https://github.com/sp00nznet/ps3recomp)** — Ned Heller
  ([@sp00nznet](https://github.com/sp00nznet)) and
  [contributors](https://github.com/sp00nznet/ps3recomp/blob/master/CONTRIBUTORS.md).
  Runtime, HLE, PPU/SPU lifters and the project template (`port/main.cpp`,
  `stubs.cpp`, `CMakeLists.txt` and `config.toml` start from it). MIT.
- **[NoahBPeterson/ps3recomp](https://github.com/NoahBPeterson/ps3recomp)**
  ([@NoahBPeterson](https://github.com/NoahBPeterson)), the inFAMOUS 1 fork.
  Several draw-engine speed-ups in this port (vertex-constant ranges, the
  per-program memo, whole-range vertex fetch, index decoding) were first
  written and measured for inFAMOUS 2 on top of that fork, and ported here.
- **The sibling ports** — [inFAMOUS 2](https://github.com/erikomis/infamous2-recomp),
  Resistance: Fall of Man, Resistance 2 and Deadpool: the toolkit this port
  builds on carries their fixes, and the launcher started from the Resistance 2
  one, with the inFAMOUS 2 picture options.

## References

- **[RPCS3](https://rpcs3.net)** — the reference for PS3 behaviour, the
  savedata and SELF formats, and the video-out gamma; never linked or shipped.
- **pfdtool** (flatz) — the PARAM.PFD format `tools/install_savedata.py`
  decrypts the Option File's one protected file with.
- **[Tauri](https://tauri.app)** — the launcher's framework.

## The game

Pro Evolution Soccer 2013 © Konami Digital Entertainment. This project is not
affiliated with Konami or Sony Interactive Entertainment, and contains no game
data: each player builds the port from their own copy.
