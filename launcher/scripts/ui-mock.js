// A fake Tauri backend so the built frontend can be looked at in a plain
// browser (docs/screenshots, and checking the pages without the game). Injected
// before the page loads:
//
//   npm run build && npx vite preview --port 4173
//   # then, e.g. with Playwright: page.addInitScript({ path: "scripts/ui-mock.js" })
//
// It answers the commands the window calls with a built port, a mounted disc,
// profiles, saves and a log, and no art (the art only ever comes from the
// player's disc). window.__UI_MOCK__ = { noBuilds: true }, { noDisc: true },
// { running: true }, { noPack: true } or { allFeatures: true } (a build with
// every variable the launcher drives), set by an earlier init script, shows
// those states instead; { lang: "en" } the English UI, { view: "advanced:log" }
// opens on that page (and tab). Without an init script, the page's query string
// sets the same flags (?view=performance&lang=en&noBuilds=1).
(() => {
  const q = new URLSearchParams(location.search);
  const fromQuery = Object.fromEntries([...q.entries()].map(([k, v]) => [k, v === "1" ? true : v]));
  const flags = window.__UI_MOCK__ || fromQuery;
  const home = "/Users/player";
  const data = `${home}/Library/Application Support/pes13-recomp`;
  const root = `${home}/Desktop/pes13-recomp`;
  const settings = {
    uiLang: flags.lang || "pt-BR", portDir: "", discPath: "", discImage: "", autoMount: true, activeProfile: "padrao",
    gameLang: "", windowSize: "", windowMode: "windowed", display: "", vsync: true, upscale: "", resScale: "", aspect: "", gameIcon: false,
    aa: "fxaa", sharpen: 0.2, aniso: 16, gammaOverride: false, gamma: 1, vibrance: 0, contrast: 1, shadows: 0, midtones: 0, highlights: 0, clarity: 0,
    vignette: 0, grain: 0, lutPath: "", lutStrength: 1, lutPreset: "", mods: [], modsDump: false, inputMode: "both", mouse: true, mouseSens: 1,
    mouseInvertY: false, mouseInvertX: false, mouseDeadzone: 30, mouseCapture: true, rumble: true, rumbleStrength: 100,
    audioVolume: 100, audioDevice: "", audioMute: false, audioElastic: true, showFps: false, vertexCache: true, vertexCacheSplit: true,
    bindChangedOnly: true, shaderCache: false, shaderAsync: false, shaderAsyncJobs: 4, shaderSyncHit: 1, frameClockUs: 1000, vblankUs: 16683,
    qos: true, putDoorbell: true, paceLogS: 0, padLog: false, telemetry: false, drainSpikeMs: 0, vcacheStats: false, keepAwake: true,
    video: true, ffmpegAvcodec: "", ffmpegAvutil: "", verboseLog: false, extraEnv: "", rebuildSteps: [], jobs: 0, saveBackupsKeep: 0,
    autoUpdateCheck: true,
  };
  // what the real build/BLUS31029/PES2013Recomp holds today
  const today = [
    "PS3_LANG", "PS3_AA", "PS3_SHARPEN", "PS3_ANISO", "PS3_DISPLAY_GAMMA", "PS3_INPUT_MAP", "PS3_INPUT_MODE", "PS3_MOUSE", "PS3_MOUSE_SENS",
    "PS3_MOUSE_INVERT_X", "PS3_MOUSE_INVERT_Y", "PS3_MOUSE_DEADZONE", "PS3_MOUSE_CAPTURE", "PS3_RUMBLE", "PS3_RUMBLE_STRENGTH", "PS3_PAD_LOG",
    "PS3RECOMP_METAL_FPS", "PS3_VERBOSE", "PS3_NO_AUDIO", "PS3_FRAMECLOCK_US", "PS3_VBLANK_US", "PS3_QOS", "GCM_PUT_DOORBELL", "RSX_PACE_LOG", "AUDIO_ELASTIC",
  ];
  const all = [...today, "smaa", "PS3_WINDOW_MODE", "PS3_WINDOW_SIZE", "PS3_DISPLAY", "PS3_VSYNC", "PS3_UPSCALE", "PS3_RES_SCALE", "PS3_ASPECT",
    "PS3_VIBRANCE", "PS3_CONTRAST", "PS3_SHADOWS", "PS3_MIDTONES", "PS3_HIGHLIGHTS", "PS3_CLARITY", "PS3_VIGNETTE", "PS3_GRAIN", "PS3_LUT",
    "PS3_LUT_STRENGTH", "PS3_LUT_PRESET", "PS3_AUDIO_VOLUME", "PS3_AUDIO_MUTE", "PS3_AUDIO_DEVICE", "PS3_MODS_DIR", "PS3_MODS", "PS3_MODS_DUMP",
    "PS3_SHADER_CACHE", "PS3_SHADER_ASYNC", "PS3_SHADER_ASYNC_JOBS", "PS3_SHADER_ASYNC_SYNC_HIT", "PS3RECOMP_ENG_VCACHE", "PS3RECOMP_ENG_VCACHE_SPLIT",
    "PS3RECOMP_ENG_VCACHE_STATS", "PS3RECOMP_METAL_BIND_ALL", "PS3_TELEMETRY", "RSX_DRAIN_SPIKE_MS", "PS3RECOMP_FFMPEG"];
  const features = flags.allFeatures ? all : today;
  const now = Math.floor(Date.now() / 1000);
  const builds = {
    root, eboot: `${root}/build/BLUS31029/PES2013Recomp`, ebootElf: `${root}/game/EBOOT.elf`, runSh: `${root}/tools/run.sh`,
    ok: true, missing: [], rebuildSh: `${root}/tools/rebuild.sh`, builtAt: now - 3600 * 3,
  };
  const mnt = `${home}/mnt_pes13`;
  const iso = `${root}/game_iso/PES 2013.iso`;
  const disc = flags.noDisc
    ? { root: null, title: "", titleId: "", appVer: "", image: null, ours: false, mounted: [], iso: null, mountPoint: mnt }
    : { root: mnt, title: "Pro Evolution Soccer 2013", titleId: "BLUS31029", appVer: "01.00", image: iso, ours: true, mounted: [], iso, mountPoint: mnt };
  const padrao = { id: "padrao", name: "padrão", kind: "builtin", root: `${root}/rpcs3`, savedata: `${root}/rpcs3/dev_hdd0/home/00000001/savedata`, readOnly: false, exists: true };
  const profiles = [
    { ...padrao, saves: 1107, bytes: 256000000, hasEdit: true, edit: { players: 8993, teams: 417, rosters: 340 }, editError: null, active: true },
    { id: "local:Brasil 2026", name: "Brasil 2026", kind: "local", root: `${data}/profiles/Brasil 2026`, savedata: "", readOnly: false, exists: true, saves: 1107, bytes: 256000000, hasEdit: true, edit: { players: 9001, teams: 417, rosters: 340 }, editError: null, active: false },
    { id: "ext:Flamengo teste", name: "Flamengo teste", kind: "external", root: `${root}/analysis/test-save-flamengo-2026/gamedata`, savedata: "", readOnly: true, exists: true, saves: 1107, bytes: 255000000, hasEdit: true, edit: null, editError: "EEDIT CRC32 mismatch", active: false },
  ];
  const slot = (name, sub, mod, bytes) => ({ name, kind: "save", title: "Pro Evolution Soccer 2013", subtitle: sub, detail: "", modified: mod, bytes, path: `/saves/${name}`, icon: null, hash: "" });
  const port = [slot("BLUS31029EEDIT", "Edit", now - 3600 * 5, 7905992), slot("BLUS31029EOPTION", "Options", now - 3600 * 5, 40000)];
  for (let n = 1; n <= 343; n++) port.push(slot(`BLUS31029EFACE${String(n).padStart(3, "0")}`, "Face", now - 86400, 131172));
  for (let n = 1; n <= 389; n++) port.push(slot(`BLUS31029EUNIFORM${String(n).padStart(3, "0")}`, "Kit", now - 86400, 262179));
  const log = [
    "[    0.02] [boot] dispatching entry OPD 0x01A95538",
    "[    0.41] [cellSysutil] system language 7 (PS3_LANG)",
    "[    0.90] [rsx] Metal backend init OK -- window open",
    "[   61.35] [RSX FPS] display=60.10 guest=60.10 avg_ms=16.60 p95_ms=17.10 max_ms=21.00 age_s=0.00",
    "[   62.10] [hle] stub sceNpSns (offline)",
  ].join("\n") + "\n";
  const answers = {
    get_settings: () => settings,
    save_settings: () => null,
    get_status: () => ({
      builds: flags.noBuilds ? { ...builds, ok: false, eboot: null, ebootElf: null, missing: ["build/BLUS31029/PES2013Recomp", "game/EBOOT.elf"], builtAt: 0 } : builds,
      disc, icon: null, background: null,
      lastSave: { name: "BLUS31029EEDIT", title: "Pro Evolution Soccer 2013", subtitle: "Edit", modified: now - 3600 * 5, folder: "/saves" },
      profile: padrao, dataPack: flags.noPack ? null : `${root}/BLUS31029_DOWNLOAD`,
      gameRunning: !!flags.running, otherGameRunning: false, rebuildRunning: false, dataRoot: data,
      hostSupported: true, os: "macos", appBundle: "/Applications/PES 2013 Launcher.app", finderIcon: false, version: "0.1.0",
      features,
    }),
    disc_status: () => disc,
    find_port_dirs: () => [builds],
    check_updates: () => ({
      sources: { git: false, branch: "", commit: "", subject: "", commitTime: 0, upstream: "", behind: 0, ahead: 0, dirty: 0, sourcesTime: 0, fetched: false, error: null },
      rebuildNeeded: false, builtAt: builds.builtAt,
      app: { current: "0.1.0", latest: null, newer: false, url: null, notes: null, disabled: true, error: null },
    }),
    steam_status: () => ({ available: true, installed: false, running: false, users: 0, added: 0 }),
    shader_cache_info: () => ({ path: `${root}/cache/msl`, bytes: 17800000, files: 2310 }),
    report_info: () => null,
    report_list: () => [],
    check_prereqs: () => {
      const ok = (name, path) => ({ level: "ok", name, message: path, key: "", vars: {}, path, optional: false });
      const msg = (level, name, key, message, vars = {}, extra = {}) => ({ level, name, message, key, vars, path: null, optional: false, ...extra });
      const checks = [
        msg("ok", "xcode-clt", "cltOk", "installed"),
        ok("cmake", "/opt/homebrew/bin/cmake"),
        ok("ninja", "/opt/homebrew/bin/ninja"),
        ok("disc", mnt),
        flags.noPack ? msg("warn", "datapack", "packMissing", "missing") : ok("datapack", `${root}/BLUS31029_DOWNLOAD`),
        ok("venv", `${home}/Desktop/deadpool-recomp/tools/.venv/bin/python`),
        ok("toolkit", `${home}/Desktop/ps3recomp-up-r8`),
        msg("ok", "savekeys", "keysOk", "there", {}, { optional: true }),
        msg("ok", "disk", "diskEnough", "22 GB free", { free: "22" }),
        ok("builds", root),
      ];
      return { supported: true, clt: true, checks, ok: true, disc: !flags.noDisc, buildsOk: !flags.noBuilds, freeGb: 22 };
    },
    profiles_list: () => ({ profiles, active: "padrao", gameRunning: !!flags.running, busy: false, keys: true, python: true }),
    list_trophies: () => {
      if (flags.noDisc) throw "no disc mounted";
      return { commId: "NPWR03760", title: "Pro Evolution Soccer 2013", trophies: [
        { id: 0, grade: "P", name: "Trophy 0", detail: "Every other trophy", hidden: false, unlockedAt: 0, icon: "" },
        { id: 1, grade: "B", name: "Trophy 1", detail: "A first one", hidden: false, unlockedAt: now - 86400, icon: "" },
        { id: 2, grade: "G", name: "Trophy 2", detail: "", hidden: true, unlockedAt: 0, icon: "" },
      ] };
    },
    saves_overview: () => ({
      port, rpcs3: [], rpcs3Users: [], rpcs3User: "00000001", backups: [], profile: "padrão", readOnly: false,
      portDir: padrao.savedata, rpcs3Dir: "/x/rpcs3", backupsDir: `${data}/save-backups/padrao`, gameRunning: !!flags.running, rpcs3Running: false,
    }),
    launch_preview: () => `cd ${root} && PES_ROOT=${root} PS3_GAMEDATA_ROOT=${root}/rpcs3 PS3_AA=fxaa PS3_SHARPEN=0.20 /usr/bin/caffeinate -i /bin/zsh ${root}/tools/run.sh > '${data}/last.log' 2>&1   # each line stamped with the seconds since launch into last.log`,
    read_game_log: () => ({ path: `${data}/last.log`, exists: true, size: log.length, modified: now - 120, text: log, truncated: false }),
    log_paths: () => ({ game: `${data}/last.log`, saves: padrao.savedata, data, sessions: `${data}/logs` }),
    take_play_request: () => false,
    take_start_view: () => flags.view || null,
    frontend_log: (a) => console.warn("frontend:", a.message),
    get_input_map: () => ({ path: `${data}/input.toml`, exists: false, bindings: { keyboard: {}, mouseButtons: {}, controller: {} } }),
    save_input_map: () => `${data}/input.toml`,
    reset_input_map: () => null,
    list_screens: () => ["Built-in Retina Display"],
    list_mods: () => ({ dir: `${data}/mods`, dumpDir: `${data}/texture-dump`, packs: [] }),
  };
  let cb = 0;
  window.__TAURI_INTERNALS__ = {
    invoke: async (cmd, args) => {
      if (cmd.startsWith("plugin:event|")) return cmd.endsWith("listen") ? ++cb : null;
      if (cmd.startsWith("plugin:dialog|")) return null;
      if (cmd === "save_settings") Object.assign(settings, args.settings);
      const f = answers[cmd];
      if (!f) {
        console.warn("ui-mock: no answer for", cmd, args);
        return null;
      }
      return f(args || {});
    },
    transformCallback: () => ++cb,
    unregisterCallback: () => {},
    convertFileSrc: (p) => p,
    metadata: { currentWindow: { label: "main" }, currentWebview: { windowLabel: "main", label: "main" } },
  };
  window.__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener: () => {} };
})();
