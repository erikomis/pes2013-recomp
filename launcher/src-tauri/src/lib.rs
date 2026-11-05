//! Launcher core for the PES 2013 (BLUS31029, update 01.04) port: the settings,
//! the Option File profiles, the player's disc, the builds of the port folder,
//! the rebuild (tools/rebuild.sh) as a child process whose output is streamed
//! to the window, and "Play", which starts tools/run.sh with the settings mapped
//! onto the port's environment variables. run.sh assembles the VFS tree, mounts
//! the disc image read-only and sets its defaults with ${VAR:-default}, so what
//! the launcher sets wins; the game then opens its own Metal window, and exec
//! keeps it under the pid Play started. No game code or data is part of the
//! app: everything it shows or starts comes from the player's own disc and
//! build folder.
//!
//! A variable is passed only when the build reads it (`FEATURE_MARKERS`: the
//! executable is searched for the name), so a control the runtime does not have
//! yet says so instead of doing nothing, and only when it differs from what
//! run.sh would do. With the defaults Play's environment is run.sh's own plus
//! PES_ROOT and the active profile's PS3_GAMEDATA_ROOT.
//!
//! The launcher's data folder also holds `keys/`. Nothing here reads it, copies
//! it, lists it or puts it in a backup, a report or a zip: only the existence of
//! `keys/savedata_keys.txt` is looked at, and its path handed to
//! tools/install_savedata.py.

mod app_icon;
mod input_map;
mod mods;
mod play_shortcut;
mod profiles;
mod report;
mod saves;
mod steam;
mod steam_art;
mod trophies;
mod update;
mod vdf;
mod zipfile;

use input_map::{Bindings, InputEnv};
use saves::{read_sfo, BackupMeta, Side, Slot};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::UNIX_EPOCH;
use tauri::{AppHandle, Emitter, Manager, State};

const TITLE_ID: &str = "BLUS31029";
/// The game's executable: it opens its own Metal window, there is no host.
const GAME_EXE: &str = "PES2013Recomp";
/// What Play starts, under the port folder.
const RUN_SH: &str = "tools/run.sh";

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

/// What the player can change. Each field maps onto one of the environment
/// variables the port reads (see `launch_env`) or onto how Play starts it.
#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase", default)]
pub struct Settings {
    /// Launcher UI language: "pt-BR" or "en".
    pub ui_lang: String,
    /// The port folder: build/BLUS31029/PES2013Recomp, game/EBOOT.elf and
    /// tools/run.sh. Empty = found on its own.
    pub port_dir: String,
    /// The disc: a folder holding PS3_GAME/, passed as PES_MOUNT when it is not
    /// run.sh's own mount point. Empty = that mount point, else a mounted
    /// BLUS31029 under /Volumes.
    pub disc_path: String,
    /// A disc image to attach when the disc is not mounted. Empty = run.sh mounts
    /// the one behind the port's game_iso.
    pub disc_image: String,
    /// Attach `disc_image` on Play when no disc is mounted.
    pub auto_mount: bool,
    /// The Option File profile Play uses (profiles.rs): "padrao", "local:<name>"
    /// or "ext:<name>". Changed only through `profile_set_active`.
    pub active_profile: String,
    /// PS3_LANG; empty = run.sh's own (PT, the title's Portuguese labels).
    pub game_lang: String,
    /// PS3_WINDOW_SIZE: "<w>x<h>"; empty = the game's 1280x720.
    pub window_size: String,
    /// PS3_WINDOW_MODE: "windowed" (the default), "fullscreen" (macOS's own)
    /// or "borderless".
    pub window_mode: String,
    /// PS3_DISPLAY: the screen's name (or its 1-based number when two share
    /// a name); empty = the main screen.
    pub display: String,
    /// PS3_VSYNC=0 when off.
    pub vsync: bool,
    /// PS3_UPSCALE: "" (a plain scale) or "metalfx" (macOS 13+).
    pub upscale: String,
    /// PS3_RES_SCALE: the internal resolution as a multiple of 1280x720,
    /// "" (native), "1.5" (1080p), "2" (1440p) or "3" (4K). Experimental.
    pub res_scale: String,
    /// PS3_ASPECT: "" (16:9, the game's own), "21:9" or "32:9".
    pub aspect: String,
    /// The player's own ICON0.PNG in the Dock instead of the placeholder.
    pub game_icon: bool,
    /// PS3_AA: "" (off), "fxaa" or "smaa" (when the build has it).
    pub aa: String,
    /// PS3_SHARPEN: 0 (off) to 1.
    pub sharpen: f32,
    /// PS3_ANISO: 0 (off), 2, 4, 8 or 16 (16 = run.sh's).
    pub aniso: u32,
    /// PS3_DISPLAY_GAMMA when set; otherwise the game's own brightness.
    pub gamma_override: bool,
    pub gamma: f32,
    /// PS3_VIBRANCE: -1 (muted) .. 0 (off) .. 1 (vivid).
    pub vibrance: f32,
    /// PS3_CONTRAST: 0.5 .. 1 (off) .. 1.5.
    pub contrast: f32,
    /// PS3_SHADOWS, PS3_MIDTONES, PS3_HIGHLIGHTS: the tone curve, each
    /// -1 .. 0 (off) .. 1. PS3_CLARITY: local contrast, the same range.
    pub shadows: f32,
    pub midtones: f32,
    pub highlights: f32,
    pub clarity: f32,
    /// PS3_VIGNETTE and PS3_GRAIN: 0 (off) .. 1.
    pub vignette: f32,
    pub grain: f32,
    /// PS3_LUT: the player's colour LUT (ReShade's PNG layout), and how much
    /// of it (PS3_LUT_STRENGTH, 0..1).
    pub lut_path: String,
    pub lut_strength: f32,
    /// PS3_LUT_PRESET: a built-in LUT ("warm", "cool", "film", "vivid"; empty =
    /// none) in place of the file, mixed in by lut_strength.
    pub lut_preset: String,
    /// PS3_MODS: the texture packs in use (folders in <data>/mods), first
    /// wins; empty = none.
    pub mods: Vec<String>,
    /// PS3_MODS_DUMP=<data>/texture-dump: the game writes every texture it
    /// uploads there, named as a pack names it.
    pub mods_dump: bool,
    /// PS3_INPUT_MODE: "both" (the default), "controller" or "keyboard".
    pub input_mode: String,
    /// PS3_MOUSE, PS3_MOUSE_SENS, PS3_MOUSE_INVERT_Y, PS3_MOUSE_INVERT_X,
    /// PS3_MOUSE_DEADZONE (the runtime's defaults: on, 1.0, off, off, 30).
    pub mouse: bool,
    pub mouse_sens: f32,
    pub mouse_invert_y: bool,
    pub mouse_invert_x: bool,
    pub mouse_deadzone: u32,
    /// PS3_MOUSE_CAPTURE: a click captures the cursor (Esc/Cmd releases it).
    pub mouse_capture: bool,
    /// PS3_RUMBLE=0 when off; PS3_RUMBLE_STRENGTH in percent (0-200).
    pub rumble: bool,
    pub rumble_strength: u32,
    /// PS3_AUDIO_VOLUME (0-100, 100 = the default), PS3_AUDIO_DEVICE (the output
    /// whose name contains it; empty = the system's default).
    pub audio_volume: u32,
    pub audio_device: String,
    /// No sound, through the best variable the build has (`mute_var`).
    pub audio_mute: bool,
    /// AUDIO_ELASTIC: a longer audio queue, so a frame that runs long does not
    /// become a gap in the sound. On in tools/run.sh; off passes AUDIO_ELASTIC=0.
    pub audio_elastic: bool,
    /// PS3RECOMP_METAL_FPS=1: frame rate and frame times in the window title.
    pub show_fps: bool,
    /// PS3RECOMP_ENG_VCACHE=0 / PS3RECOMP_ENG_VCACHE_SPLIT=0 when off.
    pub vertex_cache: bool,
    pub vertex_cache_split: bool,
    /// PS3RECOMP_METAL_BIND_ALL=1 when off.
    pub bind_changed_only: bool,
    /// PS3_SHADER_CACHE=<data>/shadercache when on. Translated shaders are on
    /// disk anyway through RSX_MSL_CACHE, which run.sh sets.
    pub shader_cache: bool,
    /// PS3_SHADER_ASYNC=1, its parallel builds (PS3_SHADER_ASYNC_JOBS, 1-8, 4 =
    /// the default) and whether a pipeline whose translation is cached builds at
    /// once (PS3_SHADER_ASYNC_SYNC_HIT 0/1/2, 1 = the default).
    pub shader_async: bool,
    pub shader_async_jobs: u32,
    pub shader_sync_hit: u32,
    /// PS3_FRAMECLOCK_US: the sleep between FIFO passes (port/main.cpp, 1000).
    pub frame_clock_us: u32,
    /// PS3_VBLANK_US: the vblank period (port/main.cpp, 16683 = 59.94 Hz).
    pub vblank_us: u32,
    /// PS3_QOS=0 when off: the game threads' user-interactive class.
    pub qos: bool,
    /// GCM_PUT_DOORBELL=0 when off: a PUT write wakes the FIFO at once.
    pub put_doorbell: bool,
    /// RSX_PACE_LOG: frame pacing into the log every this many seconds; 0 = off.
    pub pace_log_s: u32,
    /// Log switches: PS3_PAD_LOG=1, PS3_TELEMETRY=1, RSX_DRAIN_SPIKE_MS (0 =
    /// off), PS3RECOMP_ENG_VCACHE_STATS=1.
    pub pad_log: bool,
    pub telemetry: bool,
    pub drain_spike_ms: u32,
    pub vcache_stats: bool,
    /// Run under `caffeinate -i` so the Mac does not sleep mid-game.
    pub keep_awake: bool,
    /// PS3RECOMP_FFMPEG=0 when off (no movies through FFmpeg).
    pub video: bool,
    /// PS3RECOMP_FFMPEG_AVCODEC / _AVUTIL; empty = Homebrew's.
    pub ffmpeg_avcodec: String,
    pub ffmpeg_avutil: String,
    /// PS3_VERBOSE=1: the runtime's per-event lines in the log (run.sh keeps
    /// them out: millions of lines per long run).
    pub verbose_log: bool,
    /// Extra KEY=VALUE lines (diagnostics), one per line; '#' starts a comment.
    pub extra_env: String,
    /// The rebuild's steps and JOBS (Advanced > Install / rebuild).
    pub rebuild_steps: Vec<String>,
    pub jobs: u32,
    /// Automatic backups of the saves made before each "Play" that are kept.
    /// 0 = off, the default here: an Option File is about 250 MB.
    pub save_backups_keep: u32,
    /// Look for new port sources on start (when the folder is a git checkout).
    pub auto_update_check: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            ui_lang: "pt-BR".into(),
            port_dir: String::new(),
            disc_path: String::new(),
            disc_image: String::new(),
            auto_mount: true,
            active_profile: profiles::BUILTIN_ID.into(),
            game_lang: String::new(),
            window_size: String::new(),
            window_mode: "windowed".into(),
            display: String::new(),
            vsync: true,
            upscale: String::new(),
            res_scale: String::new(),
            aspect: String::new(),
            game_icon: false,
            aa: String::new(),
            sharpen: 0.0,
            aniso: 16,
            gamma_override: false,
            gamma: 1.0,
            vibrance: 0.0,
            contrast: 1.0,
            shadows: 0.0,
            midtones: 0.0,
            highlights: 0.0,
            clarity: 0.0,
            vignette: 0.0,
            grain: 0.0,
            lut_path: String::new(),
            lut_strength: 1.0,
            lut_preset: String::new(),
            mods: Vec::new(),
            mods_dump: false,
            input_mode: "both".into(),
            mouse: true,
            mouse_sens: 1.0,
            mouse_invert_y: false,
            mouse_invert_x: false,
            mouse_deadzone: 30,
            mouse_capture: true,
            rumble: true,
            rumble_strength: 100,
            audio_volume: 100,
            audio_device: String::new(),
            audio_mute: false,
            audio_elastic: true,
            show_fps: false,
            vertex_cache: true,
            vertex_cache_split: true,
            bind_changed_only: true,
            shader_cache: false,
            shader_async: false,
            shader_async_jobs: 4,
            shader_sync_hit: 1,
            frame_clock_us: FRAME_CLOCK_DEFAULT,
            vblank_us: VBLANK_DEFAULT,
            qos: true,
            put_doorbell: true,
            pace_log_s: 0,
            pad_log: false,
            telemetry: false,
            drain_spike_ms: 0,
            vcache_stats: false,
            keep_awake: true,
            video: true,
            ffmpeg_avcodec: String::new(),
            ffmpeg_avutil: String::new(),
            verbose_log: false,
            extra_env: String::new(),
            rebuild_steps: Vec::new(),
            jobs: 0,
            save_backups_keep: 0,
            auto_update_check: true,
        }
    }
}

/// port/main.cpp's defaults, passed only when changed.
const FRAME_CLOCK_DEFAULT: u32 = 1000;
const VBLANK_DEFAULT: u32 = 16683;
const ANISO_DEFAULT: u32 = 16;

fn home() -> PathBuf {
    std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("."))
}

/// The launcher's own folder: launcher.json, profiles, backups, reports, the
/// game's log. Its `keys/` is not the launcher's to read.
fn data_root() -> PathBuf {
    if cfg!(target_os = "macos") {
        home().join("Library/Application Support/pes13-recomp")
    } else {
        std::env::var_os("XDG_DATA_HOME").map(PathBuf::from).unwrap_or_else(|| home().join(".local/share")).join("pes13-recomp")
    }
}

fn settings_path() -> PathBuf {
    data_root().join("launcher.json")
}

fn reports_dir() -> PathBuf {
    data_root().join("reports")
}

/// The controls file (PS3_INPUT_MAP), next to launcher.json. It exists once
/// the Controls page has changed a binding; until then the game's built-in
/// layout applies and Play passes nothing.
fn input_map_path() -> PathBuf {
    data_root().join("input.toml")
}

/// Where texture packs live (PS3_MODS_DIR): <data>/mods.
fn mods_dir() -> PathBuf {
    data_root().join("mods")
}

/// Where "Dump textures" makes the game write them (PS3_MODS_DUMP).
fn mods_dump_dir() -> PathBuf {
    data_root().join("texture-dump")
}

/// The controls file as Play passes it (see `launch_env`).
fn input_env() -> InputEnv {
    let p = input_map_path();
    match fs::read_to_string(&p) {
        Ok(text) => InputEnv { path: Some(s(&p)), has_mouse_section: input_map::parse(&text).has_mouse_section },
        Err(_) => InputEnv::default(),
    }
}

fn rpcs3_dir() -> PathBuf {
    if cfg!(target_os = "macos") {
        home().join("Library/Application Support/rpcs3")
    } else {
        std::env::var_os("XDG_CONFIG_HOME").map(PathBuf::from).unwrap_or_else(|| home().join(".config")).join("rpcs3")
    }
}

fn load_settings_file() -> Settings {
    fs::read_to_string(settings_path()).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or_default()
}

fn write_settings(s: &Settings) -> Result<(), String> {
    let p = settings_path();
    if let Some(d) = p.parent() {
        fs::create_dir_all(d).map_err(|e| e.to_string())?;
    }
    let tmp = p.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_string_pretty(s).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())
}

fn parse_env_lines(text: &str) -> Vec<(String, String)> {
    text.lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .filter_map(|l| {
            let l = l.strip_prefix("export ").unwrap_or(l);
            let (k, v) = l.split_once('=')?;
            let k = k.trim();
            if k.is_empty() || !k.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
                return None;
            }
            Some((k.to_string(), v.trim().trim_matches('"').to_string()))
        })
        .collect()
}

fn extra_var(s: &Settings, key: &str) -> Option<String> {
    parse_env_lines(&s.extra_env).into_iter().rev().find(|(k, _)| k == key).map(|(_, v)| v)
}

fn now_secs() -> u64 {
    std::time::SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

fn now_ms() -> u64 {
    std::time::SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

fn mtime(p: &Path) -> u64 {
    fs::metadata(p).and_then(|m| m.modified()).ok().and_then(|t| t.duration_since(UNIX_EPOCH).ok()).map_or(0, |d| d.as_secs())
}

fn base64(data: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut s = String::with_capacity(data.len().div_ceil(3) * 4);
    for c in data.chunks(3) {
        let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
        s.push(T[(n >> 18) as usize & 63] as char);
        s.push(T[(n >> 12) as usize & 63] as char);
        s.push(if c.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
        s.push(if c.len() > 2 { T[n as usize & 63] as char } else { '=' });
    }
    s
}

fn data_url(path: &Path, mime: &str) -> Option<String> {
    let mut buf = Vec::new();
    fs::File::open(path).ok()?.read_to_end(&mut buf).ok()?;
    Some(format!("data:{mime};base64,{}", base64(&buf)))
}

fn s(p: &Path) -> String {
    p.to_string_lossy().into_owned()
}

// ---------------------------------------------------------------------------
// The disc
// ---------------------------------------------------------------------------

/// A folder that holds a PS3 disc's PS3_GAME/ (or is PS3_GAME itself).
fn disc_root_of(p: &Path) -> Option<PathBuf> {
    if p.join("PS3_GAME/PARAM.SFO").is_file() {
        Some(p.to_path_buf())
    } else if p.file_name().is_some_and(|n| n == "PS3_GAME") && p.join("PARAM.SFO").is_file() {
        p.parent().map(Path::to_path_buf)
    } else {
        None
    }
}

fn disc_title_id(root: &Path) -> Option<String> {
    read_sfo(&root.join("PS3_GAME/PARAM.SFO")).and_then(|v| v.get("TITLE_ID").cloned())
}

/// tools/env.sh's PES_MOUNT: where run.sh mounts the image.
fn default_mount() -> PathBuf {
    std::env::var_os("PES_MOUNT").filter(|v| !v.is_empty()).map(PathBuf::from).unwrap_or_else(|| home().join("mnt_pes13"))
}

/// The image run.sh would mount: `game_iso/*.iso` under the port, first by name
/// as zsh's glob gives it. Only looked at: nothing near that folder is written.
fn port_iso(root: &Path) -> Option<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir(root.join("game_iso"))
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|e| e == "iso"))
        .collect();
    v.sort();
    v.into_iter().next()
}

/// Mounted volumes that are this game's disc.
fn mounted_discs() -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir("/Volumes")
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| disc_title_id(p).as_deref() == Some(TITLE_ID))
        .collect();
    v.sort();
    v
}

/// The disc Play uses: the setting when it points at one, else run.sh's mount
/// point, else a mounted BLUS31029.
fn find_disc(s: &Settings) -> Option<PathBuf> {
    let p = s.disc_path.trim();
    if !p.is_empty() {
        if let Some(r) = disc_root_of(Path::new(p)) {
            return Some(r);
        }
    }
    disc_root_of(&default_mount()).or_else(|| mounted_discs().into_iter().next())
}

/// PES_MOUNT for a disc run.sh would not look for by itself.
fn mount_override(disc: Option<&Path>) -> Option<PathBuf> {
    disc.filter(|d| *d != default_mount()).map(Path::to_path_buf)
}

/// The string values of `key` in an XML plist, in order.
fn plist_strings(xml: &str, key: &str) -> Vec<String> {
    let tag = format!("<key>{key}</key>");
    let mut out = Vec::new();
    let mut rest = xml;
    while let Some(i) = rest.find(&tag) {
        rest = &rest[i + tag.len()..];
        let t = rest.trim_start();
        if let Some(v) = t.strip_prefix("<string>").and_then(|v| v.split_once("</string>")).map(|(v, _)| v) {
            out.push(v.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"));
        }
    }
    out
}

/// Disc images attached now: (image path, its mount points).
fn attached_images() -> Vec<(String, Vec<String>)> {
    if !cfg!(target_os = "macos") {
        return Vec::new();
    }
    let Some(xml) = command_stdout(Command::new("/usr/bin/hdiutil").args(["info", "-plist"])) else { return Vec::new() };
    // one <key>image-path</key> per attached image; its mount points follow
    // before the next one
    let tag = "<key>image-path</key>";
    let mut out = Vec::new();
    let parts: Vec<&str> = xml.split(tag).collect();
    for part in parts.iter().skip(1) {
        let chunk = format!("{tag}{part}");
        let image = plist_strings(&chunk, "image-path").into_iter().next().unwrap_or_default();
        out.push((image, plist_strings(&chunk, "mount-point")));
    }
    out
}

fn image_of(mount: &Path) -> Option<String> {
    let m = s(mount);
    attached_images().into_iter().find(|(_, mps)| mps.iter().any(|p| *p == m)).map(|(i, _)| i)
}

/// Attach the image read-only at run.sh's mount point (as run.sh itself does,
/// and it then finds the disc there), and return the disc's root.
fn attach_image(image: &Path) -> Result<PathBuf, String> {
    if !image.is_file() {
        return Err(format!("{}: no such file", image.display()));
    }
    if !cfg!(target_os = "macos") {
        return Err("mounting a disc image is macOS only".into());
    }
    // already attached: its mount point
    let img = s(image);
    if let Some((_, mps)) = attached_images().into_iter().find(|(i, _)| *i == img) {
        if let Some(r) = mps.iter().map(PathBuf::from).find_map(|p| disc_root_of(&p)) {
            return Ok(r);
        }
    }
    let mount = default_mount();
    if disc_root_of(&mount).is_some() {
        return Err(format!("{}: another disc is mounted there; eject it first", mount.display()));
    }
    fs::create_dir_all(&mount).map_err(|e| format!("{}: {e}", mount.display()))?;
    let out = Command::new("/usr/bin/hdiutil")
        .args(["attach", "-readonly", "-plist", "-mountpoint"])
        .arg(&mount)
        .arg(image)
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("hdiutil: {e}"))?;
    if !out.status.success() {
        return Err(format!("hdiutil attach: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    disc_root_of(&mount).ok_or_else(|| format!("{}: mounted, but it holds no PS3_GAME folder (not a PS3 disc image?)", image.display()))
}

#[derive(Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DiscInfo {
    root: Option<String>,
    title: String,
    title_id: String,
    app_ver: String,
    /// The image it is mounted from, when it is one.
    image: Option<String>,
    /// The disc is this game (BLUS31029).
    ours: bool,
    /// Other BLUS31029 volumes mounted now.
    mounted: Vec<String>,
    /// The image behind the port's game_iso, which run.sh mounts on Play.
    iso: Option<String>,
    /// run.sh's mount point.
    mount_point: String,
}

fn disc_info(s: &Settings) -> DiscInfo {
    let mut d = DiscInfo {
        mounted: mounted_discs().iter().map(|p| self::s(p)).collect(),
        iso: port_root(s).as_deref().and_then(port_iso).map(|p| self::s(&p)),
        mount_point: self::s(&default_mount()),
        ..Default::default()
    };
    if let Some(r) = find_disc(s) {
        let v = read_sfo(&r.join("PS3_GAME/PARAM.SFO")).unwrap_or_default();
        d.title = v.get("TITLE").cloned().unwrap_or_default();
        d.title_id = v.get("TITLE_ID").cloned().unwrap_or_default();
        d.app_ver = v.get("APP_VER").or(v.get("VERSION")).cloned().unwrap_or_default();
        d.ours = d.title_id == TITLE_ID;
        d.image = image_of(&r);
        d.root = Some(self::s(&r));
    }
    d
}

/// The disc's ICON0.PNG and PIC1.PNG (the player's own; nothing ships).
fn disc_art(s: &Settings) -> (Option<PathBuf>, Option<PathBuf>) {
    match find_disc(s) {
        Some(r) => {
            let g = r.join("PS3_GAME");
            (Some(g.join("ICON0.PNG")).filter(|p| p.is_file()), Some(g.join("PIC1.PNG")).filter(|p| p.is_file()))
        }
        None => (None, None),
    }
}

// ---------------------------------------------------------------------------
// The builds
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone, Debug, Default)]
#[serde(rename_all = "camelCase")]
pub struct Builds {
    root: String,
    /// build/BLUS31029/PES2013Recomp.
    eboot: Option<String>,
    /// game/EBOOT.elf, the decrypted update.
    eboot_elf: Option<String>,
    /// tools/run.sh, which Play starts.
    run_sh: Option<String>,
    /// Everything Play needs is there.
    ok: bool,
    missing: Vec<String>,
    /// tools/rebuild.sh, when this folder can rebuild.
    rebuild_sh: Option<String>,
    /// When the executable was made (its mtime).
    built_at: u64,
}

fn resolve_builds(root: &Path) -> Builds {
    let file = |p: PathBuf| Some(p).filter(|p| p.is_file());
    let eboot = file(root.join("build").join(TITLE_ID).join(GAME_EXE));
    let eboot_elf = file(root.join("game/EBOOT.elf"));
    let run_sh = file(root.join(RUN_SH));
    let mut missing = Vec::new();
    for (what, v) in [
        (format!("build/{TITLE_ID}/{GAME_EXE}"), eboot.is_some()),
        ("game/EBOOT.elf".to_string(), eboot_elf.is_some()),
        (RUN_SH.to_string(), run_sh.is_some()),
    ] {
        if !v {
            missing.push(what);
        }
    }
    let rebuild_sh = file(root.join("tools/rebuild.sh"));
    let o = |p: &Option<PathBuf>| p.as_deref().map(s);
    Builds {
        root: s(root),
        built_at: eboot.as_deref().map(mtime).unwrap_or(0),
        ok: missing.is_empty(),
        eboot: o(&eboot),
        eboot_elf: o(&eboot_elf),
        run_sh: o(&run_sh),
        missing,
        rebuild_sh: o(&rebuild_sh),
    }
}

/// The folder this launcher lives in: launcher/src-tauri/../.. holds tools/.
fn own_repo() -> Option<PathBuf> {
    let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    p.join("tools/run.sh").is_file().then(|| p.canonicalize().unwrap_or(p))
}

/// Port folders found on this Mac: PES_ROOT, the folder the launcher comes from,
/// then a folder one level under the usual places that has the build. Complete
/// builds first, the newest build first.
fn find_port_dirs_now() -> Vec<Builds> {
    let mut cands: Vec<PathBuf> = Vec::new();
    if let Some(r) = std::env::var_os("PES_ROOT") {
        cands.push(PathBuf::from(r));
    }
    cands.extend(own_repo());
    for base in ["Desktop", "Developer", "Documents", "Projects", "src", "code", "git", ""] {
        let dir = home().join(base);
        let Ok(it) = fs::read_dir(&dir) else { continue };
        for e in it.flatten() {
            let p = e.path();
            if p.join("build").join(TITLE_ID).is_dir() && !e.file_name().to_string_lossy().starts_with('.') {
                cands.push(p);
            }
        }
    }
    let mut seen = std::collections::HashSet::new();
    let mut v: Vec<Builds> = cands
        .into_iter()
        .filter(|p| p.is_dir())
        .map(|p| p.canonicalize().unwrap_or(p))
        .filter(|p| seen.insert(p.clone()))
        .map(|p| resolve_builds(&p))
        .collect();
    v.sort_by(|a, b| b.ok.cmp(&a.ok).then(b.built_at.cmp(&a.built_at)));
    v
}

/// The port folder in use: the setting, else the best one found.
fn port_root(s: &Settings) -> Option<PathBuf> {
    let p = s.port_dir.trim();
    if !p.is_empty() {
        return Some(PathBuf::from(p));
    }
    find_port_dirs_now().into_iter().find(|b| b.ok || b.rebuild_sh.is_some()).map(|b| PathBuf::from(b.root))
}

// ---------------------------------------------------------------------------
// The active profile, the data pack, the log
// ---------------------------------------------------------------------------

fn profile_store(s: &Settings) -> profiles::Store {
    profiles::Store { data: data_root(), builtin_root: port_root(s).map(|r| r.join("rpcs3")) }
}

fn active_profile(s: &Settings) -> Result<profiles::Profile, String> {
    profiles::resolve(&profile_store(s), &s.active_profile)
}

/// The saves manager's folders for a profile. Each profile has its own backups,
/// so a restore cannot put one profile's saves into another.
fn locations_of(p: &profiles::Profile) -> saves::Locations {
    saves::Locations {
        port_savedata: PathBuf::from(&p.savedata),
        rpcs3_hdd0: rpcs3_dir().join("dev_hdd0"),
        backups: data_root().join("save-backups").join(profiles::backup_key(&p.id)),
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveInfo {
    name: String,
    title: String,
    subtitle: String,
    modified: u64,
    folder: String,
}

fn last_save(s: &Settings) -> Option<SaveInfo> {
    let p = active_profile(s).ok()?;
    saves::newest_slot(Path::new(&p.savedata))
        .map(|x| SaveInfo { name: x.name, title: x.title, subtitle: x.subtitle, modified: x.modified, folder: x.path })
}

/// The data pack run.sh links into the download slot, when it is there.
fn data_pack(root: &Path) -> Option<PathBuf> {
    let p = root.join(format!("{TITLE_ID}_DOWNLOAD"));
    p.join("USRDIR").is_dir().then_some(p)
}

/// The translated shaders on disk: RSX_MSL_CACHE, run.sh's default unless the
/// extra variables move it.
fn msl_cache_dir(s: &Settings) -> Option<PathBuf> {
    extra_var(s, "RSX_MSL_CACHE").filter(|v| !v.is_empty()).map(PathBuf::from).or_else(|| port_root(s).map(|r| r.join("cache/msl")))
}

/// PS3_SHADER_CACHE, for the build that reads it.
fn shader_cache_dir() -> PathBuf {
    data_root().join("shadercache")
}

/// The game's output, each line prefixed with the seconds since launch; the
/// previous session's moves to logs/session-<date>.log, the 10 newest kept.
const LOG_NAME: &str = "last.log";
const LOG_KEEP: usize = 10;

fn sessions_dir() -> PathBuf {
    data_root().join("logs")
}

// ---------------------------------------------------------------------------
// Processes
// ---------------------------------------------------------------------------

#[derive(Default)]
pub struct AppState {
    rebuild: Mutex<Option<u32>>,
    game: Mutex<Option<u32>>,
    /// A profile being created or deleted: the install's pid, or 0 for work the
    /// launcher does itself. Play and every other save change wait for it.
    profile_job: Mutex<Option<u32>>,
    /// The report folder of the game started in debug mode, and whether that
    /// game is still running.
    report: Mutex<Option<(PathBuf, bool)>>,
    /// Where the last game this launcher started writes its output.
    last_log: Mutex<Option<PathBuf>>,
    /// The launcher's Dock icon as last set (app_icon::key; "" = the bundle's).
    dock_icon: Mutex<String>,
    play_request: Mutex<bool>,
    exit_with_game: Mutex<bool>,
    /// `--view <page>`: the page to open on (play_shortcut::start_view).
    start_view: Mutex<Option<String>>,
    /// build_features' cache.
    features: Mutex<FeatureCache>,
    /// tools/pes2013_edit.py's answers, by file, size and time.
    edit_cache: Mutex<BTreeMap<(String, u64, u64), Result<profiles::EditCounts, String>>>,
}

/// A GUI app on macOS starts with a bare PATH; Homebrew's and the usual install
/// places are added in front (tools/rebuild.sh needs cmake and ninja).
fn tool_path() -> std::ffi::OsString {
    let mut parts: Vec<PathBuf> = Vec::new();
    if cfg!(target_os = "macos") {
        parts.extend(["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin"].map(PathBuf::from));
    }
    if let Some(p) = std::env::var_os("PATH") {
        parts.extend(std::env::split_paths(&p));
    }
    parts.extend(["/usr/bin", "/bin", "/usr/sbin", "/sbin"].map(PathBuf::from));
    let mut seen = std::collections::HashSet::new();
    parts.retain(|p| seen.insert(p.clone()));
    std::env::join_paths(parts).unwrap_or_else(|_| std::env::var_os("PATH").unwrap_or_default())
}

/// The game builds and runs on macOS (Metal).
fn host_supported() -> bool {
    cfg!(target_os = "macos") || std::env::var_os("PES_ANY_HOST").is_some_and(|v| !v.is_empty())
}

fn require_supported_host() -> Result<(), String> {
    if host_supported() {
        Ok(())
    } else {
        Err(format!("the game runs on macOS only; this is {}", std::env::consts::OS))
    }
}

/// No console window for a child of this GUI app (Windows).
#[cfg(windows)]
pub(crate) fn no_console(cmd: &mut Command) -> &mut Command {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    cmd.creation_flags(CREATE_NO_WINDOW)
}
#[cfg(not(windows))]
pub(crate) fn no_console(cmd: &mut Command) -> &mut Command {
    cmd
}

fn clt_installed() -> bool {
    if !cfg!(target_os = "macos") {
        return true;
    }
    Command::new("xcode-select")
        .arg("-p")
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .map(|o| o.status.success() && Path::new(String::from_utf8_lossy(&o.stdout).trim()).is_dir())
        .unwrap_or(false)
}

fn find_in_path(name: &str) -> Option<PathBuf> {
    let file = format!("{name}{}", std::env::consts::EXE_SUFFIX);
    std::env::split_paths(&tool_path()).map(|d| d.join(&file)).find(|p| p.is_file())
}

fn find_brew() -> Option<PathBuf> {
    ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"].iter().map(PathBuf::from).find(|p| p.is_file())
}

fn brew_prefix() -> PathBuf {
    match find_brew() {
        Some(b) => b.parent().and_then(Path::parent).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("/opt/homebrew")),
        None => PathBuf::from("/opt/homebrew"),
    }
}

/// libavcodec / libavutil for a build with the run-time FFmpeg decoder: the
/// settings, else Homebrew's (the unversioned link, or the newest versioned one).
fn ffmpeg_libs(s: &Settings) -> (Option<PathBuf>, Option<PathBuf>) {
    let lib = brew_prefix().join("lib");
    let pick = |over: &str, name: &str| -> Option<PathBuf> {
        if !over.trim().is_empty() {
            return Some(PathBuf::from(over.trim()));
        }
        let plain = lib.join(format!("{name}.dylib"));
        if plain.exists() {
            return Some(plain);
        }
        let mut v: Vec<PathBuf> = fs::read_dir(&lib)
            .into_iter()
            .flatten()
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.file_name().is_some_and(|n| n.to_string_lossy().starts_with(&format!("{name}.")) && n.to_string_lossy().ends_with(".dylib")))
            .collect();
        v.sort();
        v.pop()
    };
    (pick(&s.ffmpeg_avcodec, "libavcodec"), pick(&s.ffmpeg_avutil, "libavutil"))
}

#[cfg(unix)]
fn own_process_group(cmd: &mut Command) {
    use std::os::unix::process::CommandExt;
    cmd.process_group(0); // so a stop reaches what it started too
}
#[cfg(not(unix))]
fn own_process_group(cmd: &mut Command) {
    no_console(cmd);
}

/// Stop what this launcher started, with what it started in turn: SIGTERM
/// (SIGKILL when `force`) to the process group `pid` leads; on Windows
/// `taskkill /T` (a close request to its windows; /F when `force`).
fn kill_tree(pid: u32, force: bool) {
    #[cfg(unix)]
    {
        let _ = Command::new("kill").arg(if force { "-KILL" } else { "-TERM" }).arg(format!("-{pid}")).status();
    }
    #[cfg(windows)]
    {
        let mut cmd = Command::new("taskkill");
        cmd.args(["/PID", &pid.to_string(), "/T"]);
        if force {
            cmd.arg("/F");
        }
        let _ = no_console(&mut cmd).stdout(Stdio::null()).stderr(Stdio::null()).status();
    }
    #[cfg(not(any(unix, windows)))]
    let _ = (pid, force);
}

fn command_stdout(cmd: &mut Command) -> Option<String> {
    let out = cmd.stderr(Stdio::null()).output().ok()?;
    if !out.status.success() {
        return None;
    }
    String::from_utf8(out.stdout).ok()
}

/// A process with this exact name is running (the game started from a
/// terminal). Only looked at, never signalled.
#[cfg(not(windows))]
fn process_running(name: &str) -> bool {
    Command::new("pgrep").args(["-x", name]).stdout(Stdio::null()).stderr(Stdio::null()).status().is_ok_and(|s| s.success())
}
#[cfg(windows)]
fn process_running(name: &str) -> bool {
    let image = if name.to_ascii_lowercase().ends_with(".exe") { name.to_string() } else { format!("{name}.exe") };
    let mut cmd = Command::new("tasklist");
    cmd.args(["/FI", &format!("IMAGENAME eq {image}"), "/NH", "/FO", "CSV"]);
    no_console(&mut cmd)
        .stderr(Stdio::null())
        .output()
        .is_ok_and(|o| String::from_utf8_lossy(&o.stdout).to_ascii_lowercase().contains(&format!("\"{}\"", image.to_ascii_lowercase())))
}

fn shell_quote(v: &str) -> String {
    if !v.is_empty() && v.chars().all(|c| c.is_ascii_alphanumeric() || "-_./:,=+@".contains(c)) {
        v.to_string()
    } else {
        format!("'{}'", v.replace('\'', "'\\''"))
    }
}

// ---------------------------------------------------------------------------
// Launch
// ---------------------------------------------------------------------------

/// "<w>x<h>", as PS3_WINDOW_SIZE takes it.
fn valid_window_size(v: &str) -> bool {
    let mut it = v.splitn(2, 'x').map(|n| n.parse::<u32>().ok());
    matches!((it.next(), it.next()), (Some(Some(w)), Some(Some(h))) if (320..=8192).contains(&w) && (180..=8192).contains(&h))
}

/// PS3_RES_SCALE for the `res_scale` setting: a multiple above 1 and up to 4
/// (the runtime's range, in quarter steps), or None for native (also for
/// anything unparsable).
fn res_scale_value(v: &str) -> Option<String> {
    let x: f32 = v.trim().parse().ok()?;
    (x > 1.0 && x <= 4.0).then(|| format!("{}", (x * 4.0).round() / 4.0))
}

/// PS3_ASPECT for the `aspect` setting: the wide shapes, or None for 16:9.
fn aspect_value(v: &str) -> Option<String> {
    match v.trim() {
        "21:9" | "32:9" => Some(v.trim().to_string()),
        _ => None,
    }
}

/// The built-in LUTs a build can have.
fn valid_lut_preset(v: &str) -> Option<&'static str> {
    ["warm", "cool", "film", "vivid"].into_iter().find(|p| *p == v.trim())
}

/// Which variable silences this build, best first. PS3_AUDIO_MUTE is the
/// mute other ports' runtimes have. PS3_MUTE silences at the device, and today
/// only the Windows (WASAPI) backend reads it. PS3_NO_AUDIO is what the macOS
/// build has: the title is told audio is unavailable and takes its silent path,
/// so it can behave differently from a game that is merely quiet.
fn mute_var(features: &Features) -> Option<&'static str> {
    ["PS3_AUDIO_MUTE", "PS3_MUTE", "PS3_NO_AUDIO"].into_iter().find(|m| features.contains(*m))
}

/// The environment Play gives tools/run.sh, on top of the launcher's own. Only
/// what the build reads (`features`), and only what differs from run.sh's and
/// the runtime's defaults; the extra variables last (they win). `gamedata`: the
/// active profile's root. `disc`: PES_MOUNT, for a disc run.sh would not find.
/// `input`: the controls file, when the Controls page has written one.
fn launch_env(s: &Settings, port: &Path, gamedata: &Path, disc: Option<&Path>, input: &InputEnv, features: &Features) -> Vec<(String, String)> {
    let mut env: Vec<(String, String)> = Vec::new();
    env.push(("PES_ROOT".into(), self::s(port)));
    env.push(("PS3_GAMEDATA_ROOT".into(), self::s(gamedata)));
    if let Some(d) = disc {
        env.push(("PES_MOUNT".into(), self::s(d)));
    }
    let mut set = |k: &str, v: String| {
        if features.contains(k) {
            env.push((k.to_string(), v));
        }
    };
    if s.video {
        let (codec, util) = ffmpeg_libs(s);
        if let Some(c) = codec {
            set("PS3RECOMP_FFMPEG_AVCODEC", self::s(&c));
        }
        if let Some(u) = util {
            set("PS3RECOMP_FFMPEG_AVUTIL", self::s(&u));
        }
    } else {
        set("PS3RECOMP_FFMPEG", "0".into());
    }
    let lang = s.game_lang.trim();
    if !lang.is_empty() && lang.len() <= 8 && lang.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        set("PS3_LANG", lang.to_string());
    }
    if s.aa == "fxaa" || (s.aa == "smaa" && features.contains("smaa")) {
        set("PS3_AA", s.aa.clone());
    }
    if s.sharpen >= 0.005 {
        set("PS3_SHARPEN", format!("{:.2}", s.sharpen.min(1.0)));
    }
    if s.aniso != ANISO_DEFAULT {
        // run.sh's ${PS3_ANISO:-16} keeps a 0
        set("PS3_ANISO", s.aniso.min(16).to_string());
    }
    if s.gamma_override {
        set("PS3_DISPLAY_GAMMA", format!("{:.2}", s.gamma.clamp(0.5, 1.5)));
    }
    // The present pass's filters: only what differs from the game's picture.
    if s.vibrance.abs() >= 0.005 {
        set("PS3_VIBRANCE", format!("{:.2}", s.vibrance.clamp(-1.0, 1.0)));
    }
    if (s.contrast - 1.0).abs() >= 0.005 && s.contrast > 0.0 {
        set("PS3_CONTRAST", format!("{:.2}", s.contrast.clamp(0.5, 1.5)));
    }
    for (k, v) in [("PS3_SHADOWS", s.shadows), ("PS3_MIDTONES", s.midtones), ("PS3_HIGHLIGHTS", s.highlights), ("PS3_CLARITY", s.clarity)] {
        if v.abs() >= 0.005 {
            set(k, format!("{:.2}", v.clamp(-1.0, 1.0)));
        }
    }
    if s.vignette >= 0.005 {
        set("PS3_VIGNETTE", format!("{:.2}", s.vignette.min(1.0)));
    }
    if s.grain >= 0.005 {
        set("PS3_GRAIN", format!("{:.2}", s.grain.min(1.0)));
    }
    let lut = s.lut_path.trim();
    let preset = valid_lut_preset(&s.lut_preset);
    if !lut.is_empty() {
        set("PS3_LUT", lut.to_string());
    }
    if let Some(p) = preset {
        set("PS3_LUT_PRESET", p.into());
    }
    if (preset.is_some() || !lut.is_empty()) && s.lut_strength < 0.995 {
        set("PS3_LUT_STRENGTH", format!("{:.2}", s.lut_strength.clamp(0.0, 1.0)));
    }
    if let Some(k) = res_scale_value(&s.res_scale) {
        set("PS3_RES_SCALE", k);
    }
    if let Some(a) = aspect_value(&s.aspect) {
        set("PS3_ASPECT", a);
    }
    // Texture packs: the folder and the enabled ones, first wins; the dump.
    if let Some(list) = mods::env_list(&s.mods) {
        set("PS3_MODS_DIR", self::s(&mods_dir()));
        set("PS3_MODS", list);
    }
    if s.mods_dump {
        set("PS3_MODS_DUMP", self::s(&mods_dump_dir()));
    }
    // The game's own window.
    if matches!(s.window_mode.as_str(), "fullscreen" | "borderless") {
        set("PS3_WINDOW_MODE", s.window_mode.clone());
    }
    if valid_window_size(&s.window_size) {
        set("PS3_WINDOW_SIZE", s.window_size.clone());
    }
    let display = s.display.trim();
    if !display.is_empty() && !display.contains(['\n', '\r']) {
        set("PS3_DISPLAY", display.to_string());
    }
    if !s.vsync {
        set("PS3_VSYNC", "0".into());
    }
    if s.upscale == "metalfx" {
        set("PS3_UPSCALE", "metalfx".into());
    }
    // Input: the controls file, then the mouse and rumble settings. The
    // variables win over the file's [mouse]; when the file has one (a hand
    // edit), every mouse setting is passed so the launcher's stand.
    if let Some(p) = &input.path {
        set("PS3_INPUT_MAP", p.clone());
    }
    if matches!(s.input_mode.as_str(), "controller" | "keyboard") {
        set("PS3_INPUT_MODE", s.input_mode.clone());
    }
    let all = input.has_mouse_section;
    if !s.mouse {
        set("PS3_MOUSE", "0".into());
    } else {
        if all {
            set("PS3_MOUSE", "1".into());
        }
        if all || (s.mouse_sens - 1.0).abs() > 1e-3 {
            set("PS3_MOUSE_SENS", format!("{:.2}", s.mouse_sens.clamp(0.05, 10.0)));
        }
        if all || s.mouse_invert_y {
            set("PS3_MOUSE_INVERT_Y", if s.mouse_invert_y { "1" } else { "0" }.into());
        }
        if all || s.mouse_invert_x {
            set("PS3_MOUSE_INVERT_X", if s.mouse_invert_x { "1" } else { "0" }.into());
        }
        if all || s.mouse_deadzone != 30 {
            set("PS3_MOUSE_DEADZONE", s.mouse_deadzone.min(120).to_string());
        }
        if all || !s.mouse_capture {
            set("PS3_MOUSE_CAPTURE", if s.mouse_capture { "1" } else { "0" }.into());
        }
    }
    if !s.rumble {
        set("PS3_RUMBLE", "0".into());
    } else if s.rumble_strength != 100 {
        set("PS3_RUMBLE_STRENGTH", s.rumble_strength.min(200).to_string());
    }
    // Audio: any value of these turns them on, so they are passed only when on.
    if s.audio_mute {
        if let Some(k) = mute_var(features) {
            set(k, "1".into());
        }
    } else if s.audio_volume < 100 {
        set("PS3_AUDIO_VOLUME", s.audio_volume.to_string());
    }
    let device = s.audio_device.trim();
    if !device.is_empty() && !device.contains(['\n', '\r']) {
        set("PS3_AUDIO_DEVICE", device.to_string());
    }
    // run.sh's ${AUDIO_ELASTIC:-1}; the runtime reads it with atoi, so 0 is off
    if !s.audio_elastic {
        set("AUDIO_ELASTIC", "0".into());
    }
    if s.show_fps {
        set("PS3RECOMP_METAL_FPS", "1".into()); // exactly "1"
    }
    if s.pad_log {
        set("PS3_PAD_LOG", "1".into());
    }
    if s.telemetry {
        set("PS3_TELEMETRY", "1".into());
    }
    if s.drain_spike_ms > 0 {
        set("RSX_DRAIN_SPIKE_MS", s.drain_spike_ms.min(60_000).to_string());
    }
    if s.vcache_stats {
        set("PS3RECOMP_ENG_VCACHE_STATS", "1".into());
    }
    if s.pace_log_s > 0 {
        set("RSX_PACE_LOG", s.pace_log_s.min(3600).to_string());
    }
    if s.shader_cache {
        set("PS3_SHADER_CACHE", self::s(&shader_cache_dir()));
    }
    if s.shader_async {
        set("PS3_SHADER_ASYNC", "1".into());
        if s.shader_async_jobs != 4 {
            set("PS3_SHADER_ASYNC_JOBS", s.shader_async_jobs.clamp(1, 8).to_string());
        }
        if s.shader_sync_hit != 1 {
            set("PS3_SHADER_ASYNC_SYNC_HIT", s.shader_sync_hit.min(2).to_string());
        }
    }
    // the draw engine: only what differs from the runtime's defaults
    if !s.vertex_cache {
        set("PS3RECOMP_ENG_VCACHE", "0".into());
    } else if !s.vertex_cache_split {
        set("PS3RECOMP_ENG_VCACHE_SPLIT", "0".into());
    }
    if !s.bind_changed_only {
        set("PS3RECOMP_METAL_BIND_ALL", "1".into());
    }
    // the port's frame clock and thread class (port/main.cpp)
    if s.frame_clock_us > 0 && s.frame_clock_us != FRAME_CLOCK_DEFAULT {
        set("PS3_FRAMECLOCK_US", s.frame_clock_us.clamp(10, 16000).to_string());
    }
    if s.vblank_us > 0 && s.vblank_us != VBLANK_DEFAULT {
        set("PS3_VBLANK_US", s.vblank_us.clamp(4000, 40000).to_string());
    }
    if !s.qos {
        set("PS3_QOS", "0".into());
    }
    if !s.put_doorbell {
        set("GCM_PUT_DOORBELL", "0".into());
    }
    if s.verbose_log {
        set("PS3_VERBOSE", "1".into());
    }
    env.extend(parse_env_lines(&s.extra_env));
    env
}

/// The program and arguments: [caffeinate -i] zsh tools/run.sh. run.sh ends in
/// exec, so the game keeps this pid and this process group.
fn launch_argv(s: &Settings, b: &Builds) -> Result<Vec<String>, String> {
    let run = b.run_sh.clone().ok_or_else(|| format!("{RUN_SH} is missing in {}", b.root))?;
    let mut argv = Vec::new();
    if s.keep_awake && Path::new("/usr/bin/caffeinate").is_file() {
        argv.extend(["/usr/bin/caffeinate".to_string(), "-i".to_string()]);
    }
    argv.extend(["/bin/zsh".to_string(), run]);
    Ok(argv)
}

/// The equivalent command line, shown in Advanced > Environment.
#[tauri::command]
fn launch_preview(state: State<'_, AppState>, settings: Settings) -> Result<String, String> {
    let root = port_root(&settings).ok_or("no port folder yet (Advanced > Install / rebuild)")?;
    let b = resolve_builds(&root);
    let features = feature_set(&b, &state.features);
    let profile = profiles::resolve(&profile_store(&settings), &load_settings_file().active_profile)?;
    let disc = find_disc(&settings);
    let over = mount_override(disc.as_deref());
    let env = launch_env(&settings, &root, Path::new(&profile.root), over.as_deref(), &input_env(), &features);
    let mut out = vec![format!("cd {} &&", shell_quote(&s(&root)))];
    out.extend(env.into_iter().map(|(k, v)| format!("{k}={}", shell_quote(&v))));
    out.extend(launch_argv(&settings, &b).unwrap_or_else(|e| vec![format!("# {e}")]).iter().map(|a| shell_quote(a)));
    out.push(format!("> {} 2>&1", shell_quote(&s(&data_root().join(LOG_NAME)))));
    out.push(format!("  # each line stamped with the seconds since launch into {LOG_NAME}"));
    Ok(out.join(" "))
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayStarted {
    log: String,
    backup: Option<String>,
    backup_error: Option<String>,
    report: Option<String>,
    /// The disc was mounted from the remembered image for this game.
    mounted: Option<String>,
    /// The profile it plays with.
    profile: String,
    /// Where the previous session's log went (logs/session-<date>.log).
    previous_log: Option<String>,
}

/// Local "YYYYMMDD-HHMMSS" of a file's modification time; UTC when `date` cannot
/// tell.
fn local_stamp(secs: u64) -> String {
    if cfg!(unix) {
        if let Some(v) = command_stdout(Command::new("/bin/date").args(["-r", &secs.to_string(), "+%Y%m%d-%H%M%S"])) {
            let v = v.trim();
            if v.len() == 15 && v.bytes().all(|b| b.is_ascii_digit() || b == b'-') {
                return v.to_string();
            }
        }
    }
    saves::stamp(secs)
}

/// A non-empty `log` moves to `<logs>/session-<its mtime>.log`, and only the
/// `keep` newest session logs stay. Returns where the old log went.
fn rotate_log(log: &Path, logs: &Path, keep: usize) -> Option<PathBuf> {
    let moved = match fs::metadata(log) {
        Ok(m) if m.len() > 0 => {
            let _ = fs::create_dir_all(logs);
            let base = format!("session-{}", local_stamp(mtime(log)));
            let mut to = logs.join(format!("{base}.log"));
            let mut n = 1;
            while to.exists() {
                n += 1;
                to = logs.join(format!("{base}-{n}.log"));
            }
            fs::rename(log, &to).ok().map(|_| to)
        }
        _ => None,
    };
    let mut old: Vec<(u64, PathBuf)> = fs::read_dir(logs)
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.file_name().is_some_and(|n| n.to_string_lossy().starts_with("session-") && n.to_string_lossy().ends_with(".log")))
        .map(|p| (mtime(&p), p))
        .collect();
    old.sort_by(|a, b| b.cmp(a));
    for (_, p) in old.into_iter().skip(keep) {
        let _ = fs::remove_file(p);
    }
    moved
}

/// Copy `raw` (the game's output, still being written) into `out` line by
/// line, each prefixed with the seconds since `t0` ("[  123.45] "); stops once
/// `done` is set and the file has nothing more, then deletes `raw`.
fn stamp_log(raw: PathBuf, mut out: fs::File, t0: std::time::Instant, done: std::sync::Arc<std::sync::atomic::AtomicBool>) {
    use std::io::Write;
    use std::sync::atomic::Ordering;
    let Ok(mut f) = fs::File::open(&raw) else { return };
    let mut buf = vec![0u8; 64 * 1024];
    let mut pending: Vec<u8> = Vec::new();
    let line = |out: &mut fs::File, data: &[u8]| {
        let _ = write!(out, "[{:8.2}] ", t0.elapsed().as_secs_f64());
        let _ = out.write_all(data);
        let _ = out.write_all(b"\n");
    };
    loop {
        let finished = done.load(Ordering::SeqCst);
        let n = f.read(&mut buf).unwrap_or(0);
        if n > 0 {
            pending.extend_from_slice(&buf[..n]);
            while let Some(i) = pending.iter().position(|&b| b == b'\n') {
                let rest = pending.split_off(i + 1);
                line(&mut out, &pending[..i]);
                pending = rest;
            }
            continue;
        }
        if finished {
            break;
        }
        let _ = out.flush();
        thread::sleep(std::time::Duration::from_millis(200));
    }
    if !pending.is_empty() {
        line(&mut out, &pending);
    }
    let _ = out.flush();
    let _ = fs::remove_file(&raw);
}

/// Start the game. `diagnostic`: debug mode (report.rs), with its log and
/// dumps in a new report folder. A refusal is also written to stderr.
#[tauri::command]
fn play(app: AppHandle, state: State<'_, AppState>, diagnostic: Option<bool>) -> Result<PlayStarted, String> {
    let r = start_game(app, state, diagnostic);
    match &r {
        Ok(p) => eprintln!("[launcher] Play: started, log {}", p.log),
        Err(e) => eprintln!("[launcher] Play refused: {e}"),
    }
    r
}

fn start_game(app: AppHandle, state: State<'_, AppState>, diagnostic: Option<bool>) -> Result<PlayStarted, String> {
    require_supported_host()?;
    let mut slot = state.game.lock().unwrap();
    if slot.is_some() {
        return Err("the game is already running".into());
    }
    // one game at a time, on this Mac: a terminal or another session may own it
    if process_running(GAME_EXE) {
        return Err("other-running".into());
    }
    if state.rebuild.lock().unwrap().is_some() {
        return Err("a rebuild is running".into());
    }
    if state.profile_job.lock().unwrap().is_some() {
        return Err("an Option File profile is being changed: wait for it to finish".into());
    }
    let s = load_settings_file();
    let root = port_root(&s).ok_or("no port folder: pick it in Advanced > Install / rebuild")?;
    let b = resolve_builds(&root);
    if !b.ok {
        return Err(format!("missing in {}: {}", b.root, b.missing.join(", ")));
    }
    let profile = active_profile(&s)?;
    if !profile.exists {
        return Err(format!("the Option File profile {}: {} is not there", profile.name, profile.root));
    }
    let mut mounted = None;
    let disc = match find_disc(&s) {
        Some(d) => Some(d),
        None if s.auto_mount && !s.disc_image.trim().is_empty() => {
            let d = attach_image(Path::new(s.disc_image.trim()))?;
            mounted = Some(self::s(&d));
            Some(d)
        }
        // run.sh mounts it
        None if port_iso(&root).is_some() => None,
        None => return Err("no-disc".into()),
    };
    if let Some(d) = &disc {
        if disc_title_id(d).as_deref() != Some(TITLE_ID) {
            return Err(format!("{}: not a {TITLE_ID} disc", d.display()));
        }
    }
    let data = data_root();
    fs::create_dir_all(data.join("logs")).map_err(|e| format!("{}: {e}", data.display()))?;
    let features = feature_set(&b, &state.features);
    let report_dir = if diagnostic.unwrap_or(false) { Some(report::create(&reports_dir(), &saves::stamp(now_secs()))?) } else { None };
    // last.log: the previous session's moves to logs/; a debug session keeps
    // its log in its own folder
    let previous_log = if report_dir.is_none() { rotate_log(&data.join(LOG_NAME), &sessions_dir(), LOG_KEEP) } else { None };
    let log_path = match &report_dir {
        Some(d) => d.join(report::LOG),
        None => data.join(LOG_NAME),
    };
    // the game writes <log>.raw; a thread stamps each line into <log>
    let raw_path = log_path.with_extension("log.raw");
    let stamped = fs::File::create(&log_path).map_err(|e| format!("{}: {e}", log_path.display()))?;
    let log = fs::File::create(&raw_path).map_err(|e| format!("{}: {e}", raw_path.display()))?;
    let log2 = log.try_clone().map_err(|e| e.to_string())?;

    // the saves as they are now, before the game can touch them (off by default)
    let (backup, backup_error) = match saves::backup_before_play(&locations_of(&profile), s.save_backups_keep, now_secs()) {
        Ok(b) => (b.map(|b| b.id), None),
        Err(e) => (None, Some(e)),
    };

    let argv = launch_argv(&s, &b)?;
    let over = mount_override(disc.as_deref());
    let mut env = launch_env(&s, &root, Path::new(&profile.root), over.as_deref(), &input_env(), &features);
    if let Some(d) = &report_dir {
        env.extend(report::env(d, features.contains("RSX_ENGINE_PASS_DUMP_TRIGGER"))); // after the extra variables: the report's paths win
    }
    let mut cmd = Command::new(&argv[0]);
    cmd.args(&argv[1..])
        .current_dir(&root)
        .env("PATH", tool_path())
        .env_remove("PS3RECOMP_METAL_HEADLESS")
        .env_remove("PS3_ARGV")
        .stdin(Stdio::null())
        .stdout(log)
        .stderr(log2);
    for (k, v) in &env {
        cmd.env(k, v);
    }
    own_process_group(&mut cmd);
    let mut child = cmd.spawn().map_err(|e| {
        let _ = fs::remove_file(&raw_path);
        format!("{}: {e}", argv[0])
    })?;
    *slot = Some(child.id());
    drop(slot);
    let done = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let stamper = {
        let (raw, done, t0) = (raw_path.clone(), done.clone(), std::time::Instant::now());
        thread::spawn(move || stamp_log(raw, stamped, t0, done))
    };
    *state.last_log.lock().unwrap() = Some(log_path.clone());
    let started = now_secs();
    if let Some(d) = &report_dir {
        *state.report.lock().unwrap() = Some((d.clone(), true));
        session_event(d, "start", &format!("pid={}", child.id()));
        let (d2, b2, disc2, now) = (d.clone(), b.clone(), disc.clone(), started);
        let env2 = env.clone();
        let argv2 = argv.clone();
        thread::spawn(move || {
            let _ = fs::write(d2.join(report::SYSTEM), system_info(&b2, disc2.as_deref(), &env2, &argv2, now));
        });
        spawn_ticker(app.clone(), d.clone());
    }
    let a = app.clone();
    let session = report_dir.clone();
    thread::spawn(move || {
        let status = child.wait();
        let code = status.as_ref().ok().and_then(|s| s.code()).unwrap_or(-1);
        // the rest of the output into the log before anyone reads it
        done.store(true, std::sync::atomic::Ordering::SeqCst);
        let _ = stamper.join();
        let st = a.state::<AppState>();
        *st.game.lock().unwrap() = None;
        if let Some((_, live)) = st.report.lock().unwrap().as_mut() {
            *live = false;
        }
        let _ = a.emit("game-exit", code);
        let debug = session.is_some();
        if let Some(d) = session {
            session_exit(&d, status.ok(), started);
            let _ = a.emit("report-changed", ());
        }
        if code == 0 && !debug && *st.exit_with_game.lock().unwrap() {
            a.exit(0);
        }
    });
    Ok(PlayStarted {
        log: self::s(&log_path),
        backup,
        backup_error,
        report: report_dir.map(|d| self::s(&d)),
        mounted,
        profile: profile.name,
        previous_log: previous_log.map(|p| self::s(&p)),
    })
}

/// Stop: SIGTERM to the process group Play started; if that group is still
/// there 8 s later it gets SIGKILL. Only this launcher's own group, by its pid,
/// never by name.
#[tauri::command]
fn stop_game(app: AppHandle, state: State<'_, AppState>) {
    if let Some(pid) = *state.game.lock().unwrap() {
        if let Some((d, true)) = state.report.lock().unwrap().clone() {
            session_event(&d, "stop", "");
        }
        kill_tree(pid, false);
        thread::spawn(move || {
            thread::sleep(std::time::Duration::from_secs(8));
            if *app.state::<AppState>().game.lock().unwrap() == Some(pid) {
                kill_tree(pid, true);
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status {
    builds: Option<Builds>,
    disc: DiscInfo,
    icon: Option<String>,
    background: Option<String>,
    last_save: Option<SaveInfo>,
    /// The Option File profile Play uses.
    profile: Option<profiles::Profile>,
    /// The data pack's folder, when it is there.
    data_pack: Option<String>,
    game_running: bool,
    /// A PES2013Recomp this launcher did not start (a terminal, another session).
    other_game_running: bool,
    rebuild_running: bool,
    data_root: String,
    host_supported: bool,
    os: String,
    app_bundle: Option<String>,
    finder_icon: bool,
    version: String,
    /// FEATURE_MARKERS found in the build.
    features: Vec<String>,
}

#[tauri::command]
async fn get_status(app: AppHandle, state: State<'_, AppState>) -> Result<Status, String> {
    let s = load_settings_file();
    let game_running = state.game.lock().unwrap().is_some();
    let rebuild_running = state.rebuild.lock().unwrap().is_some();
    let app2 = app.clone();
    let st = tauri::async_runtime::spawn_blocking(move || {
        let root = port_root(&s);
        let builds = root.as_deref().map(resolve_builds);
        let features = builds.as_ref().map(|b| build_features(b, &app2.state::<AppState>().features)).unwrap_or_default();
        let (icon, pic1) = disc_art(&s);
        sync_app_icon(&app2);
        let bundle = app_icon::app_bundle().filter(|_| cfg!(target_os = "macos"));
        let d = disc_info(&s);
        let ls = last_save(&s);
        let orun = !game_running && process_running(GAME_EXE);
        Status {
            builds,
            disc: d,
            icon: icon.and_then(|p| data_url(&p, "image/png")),
            background: pic1.and_then(|p| data_url(&p, "image/png")),
            last_save: ls,
            profile: active_profile(&s).ok(),
            data_pack: root.as_deref().and_then(data_pack).map(|p| self::s(&p)),
            game_running,
            other_game_running: orun,
            rebuild_running,
            data_root: self::s(&data_root()),
            host_supported: host_supported(),
            os: std::env::consts::OS.into(),
            finder_icon: bundle.as_deref().is_some_and(app_icon::has_finder_icon),
            app_bundle: bundle.map(|b| self::s(&b)),
            version: env!("CARGO_PKG_VERSION").into(),
            features,
        }
    })
    .await
    .map_err(|e| e.to_string())?;
    Ok(st)
}

// ---------------------------------------------------------------------------
// What the build supports
// ---------------------------------------------------------------------------

/// Names whose presence in the build's executable (as a NUL-terminated string)
/// says that it has what a control drives. A control whose name is missing says
/// it is unavailable, and `launch_env` does not pass a variable nothing reads.
/// "smaa" is the value PS3_AA would compare against.
const FEATURE_MARKERS: &[&str] = &[
    // read by the runtime today
    "PS3_LANG",
    "PS3_AA",
    "PS3_SHARPEN",
    "PS3_ANISO",
    "PS3_DISPLAY_GAMMA",
    "PS3_INPUT_MAP",
    "PS3_INPUT_MODE",
    "PS3_MOUSE",
    "PS3_MOUSE_SENS",
    "PS3_MOUSE_INVERT_X",
    "PS3_MOUSE_INVERT_Y",
    "PS3_MOUSE_DEADZONE",
    "PS3_MOUSE_CAPTURE",
    "PS3_RUMBLE",
    "PS3_RUMBLE_STRENGTH",
    "PS3_PAD_LOG",
    "PS3RECOMP_METAL_FPS",
    "PS3_VERBOSE",
    "PS3_NO_AUDIO",
    // the port's own (port/main.cpp, cellAudio.c)
    "PS3_FRAMECLOCK_US",
    "PS3_VBLANK_US",
    "PS3_QOS",
    "GCM_PUT_DOORBELL",
    "RSX_PACE_LOG",
    "AUDIO_ELASTIC",
    // in the toolkit but not always in the build
    "PS3_MUTE",
    "PS3RECOMP_FFMPEG",
    "PS3RECOMP_FFMPEG_AVCODEC",
    "PS3RECOMP_FFMPEG_AVUTIL",
    "RSX_ENGINE_PASS_DUMP_TRIGGER",
    // to be ported to this runtime
    "smaa",
    "PS3_WINDOW_MODE",
    "PS3_WINDOW_SIZE",
    "PS3_DISPLAY",
    "PS3_VSYNC",
    "PS3_UPSCALE",
    "PS3_RES_SCALE",
    "PS3_ASPECT",
    "PS3_VIBRANCE",
    "PS3_CONTRAST",
    "PS3_SHADOWS",
    "PS3_MIDTONES",
    "PS3_HIGHLIGHTS",
    "PS3_CLARITY",
    "PS3_VIGNETTE",
    "PS3_GRAIN",
    "PS3_LUT",
    "PS3_LUT_STRENGTH",
    "PS3_LUT_PRESET",
    "PS3_AUDIO_VOLUME",
    "PS3_AUDIO_MUTE",
    "PS3_AUDIO_DEVICE",
    "PS3_MODS_DIR",
    "PS3_MODS",
    "PS3_MODS_DUMP",
    "PS3_SHADER_CACHE",
    "PS3_SHADER_ASYNC",
    "PS3_SHADER_ASYNC_JOBS",
    "PS3_SHADER_ASYNC_SYNC_HIT",
    "PS3RECOMP_ENG_VCACHE",
    "PS3RECOMP_ENG_VCACHE_SPLIT",
    "PS3RECOMP_ENG_VCACHE_STATS",
    "PS3RECOMP_METAL_BIND_ALL",
    "PS3_TELEMETRY",
    "RSX_DRAIN_SPIKE_MS",
];

type Features = BTreeSet<String>;

/// The markers found in `data`: a marker counts as a whole word right before a
/// NUL, the end of a C string. One pass over the bytes: the executable is over
/// 500 MB, and a search per marker would take many seconds.
fn markers_in(data: &[u8], found: &mut Features) {
    const MAX: usize = 40;
    let tails: std::collections::HashSet<[u8; 4]> =
        FEATURE_MARKERS.iter().map(|m| { let b = m.as_bytes(); [b[b.len() - 4], b[b.len() - 3], b[b.len() - 2], b[b.len() - 1]] }).collect();
    for i in 4..data.len() {
        if data[i] != 0 || !(data[i - 1].is_ascii_alphanumeric() || data[i - 1] == b'_') {
            continue;
        }
        let tail = [data[i - 4], data[i - 3], data[i - 2], data[i - 1]];
        if !tails.contains(&tail) {
            continue;
        }
        let word = &data[i.saturating_sub(MAX)..i];
        for m in FEATURE_MARKERS {
            if word.ends_with(m.as_bytes()) {
                // the whole word, not a longer name that ends the same way
                let before = i.checked_sub(m.len() + 1).map(|j| data[j]);
                if before.is_none_or(|c| !(c.is_ascii_alphanumeric() || c == b'_')) {
                    found.insert((*m).to_string());
                }
            }
        }
    }
}

/// `markers_in` over a file, read in pieces with an overlap for a name that
/// falls across two of them.
fn scan_markers(path: &Path) -> Features {
    let mut found = Features::new();
    let Ok(mut f) = fs::File::open(path) else { return found };
    let mut buf = vec![0u8; 8 << 20];
    let mut keep = 0;
    loop {
        let n = match f.read(&mut buf[keep..]) {
            Ok(0) | Err(_) => break,
            Ok(n) => n,
        };
        let have = keep + n;
        markers_in(&buf[..have], &mut found);
        keep = have.min(64);
        buf.copy_within(have - keep..have, 0);
    }
    found
}

type FeatureCache = BTreeMap<String, (u64, u64, Vec<String>)>;

/// The markers in the build's executable, cached by path, size and mtime, in
/// memory and in `<data>/build-features.json` (a scan reads the whole file).
fn build_features(b: &Builds, cache: &Mutex<FeatureCache>) -> Vec<String> {
    build_features_in(b, cache, &data_root().join("build-features.json"))
}

fn build_features_in(b: &Builds, cache: &Mutex<FeatureCache>, file: &Path) -> Vec<String> {
    let Some(p) = &b.eboot else { return Vec::new() };
    let meta = fs::metadata(p).ok();
    let key = (meta.as_ref().map_or(0, |m| m.len()), meta.as_ref().map_or(0, mtime_of));
    if let Some(c) = cache.lock().unwrap().get(p).filter(|c| (c.0, c.1) == key) {
        return c.2.clone();
    }
    let mut disk: FeatureCache = fs::read_to_string(file).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default();
    let v = match disk.get(p).filter(|c| (c.0, c.1) == key) {
        Some(c) => c.2.clone(),
        None => {
            let v: Vec<String> = scan_markers(Path::new(p)).into_iter().collect();
            disk.insert(p.clone(), (key.0, key.1, v.clone()));
            if let Some(d) = file.parent() {
                let _ = fs::create_dir_all(d);
            }
            let _ = serde_json::to_string(&disk).map(|t| fs::write(file, t));
            v
        }
    };
    cache.lock().unwrap().insert(p.clone(), (key.0, key.1, v.clone()));
    v
}

fn feature_set(b: &Builds, cache: &Mutex<FeatureCache>) -> Features {
    build_features(b, cache).into_iter().collect()
}

fn mtime_of(m: &fs::Metadata) -> u64 {
    m.modified().ok().and_then(|t| t.duration_since(UNIX_EPOCH).ok()).map(|d| d.as_secs()).unwrap_or(0)
}

// ---------------------------------------------------------------------------
// Controls, screens, texture packs
// ---------------------------------------------------------------------------

/// The controls file for the Controls page: what it binds (the page fills in
/// the defaults for the rest), and where it is.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InputMapView {
    path: String,
    exists: bool,
    bindings: Bindings,
}

#[tauri::command]
fn get_input_map() -> InputMapView {
    let p = input_map_path();
    let text = fs::read_to_string(&p);
    InputMapView { path: s(&p), exists: text.is_ok(), bindings: text.map(|t| input_map::parse(&t).bindings).unwrap_or_default() }
}

/// Write the bindings into `path`; the file's other sections ([mouse],
/// anything newer) stay as they were.
fn write_input_map(path: &Path, bindings: Bindings) -> Result<(), String> {
    input_map::validate(&bindings)?;
    let mut file = fs::read_to_string(path).map(|t| input_map::parse(&t)).unwrap_or_default();
    file.bindings = bindings;
    if let Some(d) = path.parent() {
        fs::create_dir_all(d).map_err(|e| e.to_string())?;
    }
    let tmp = path.with_extension("toml.tmp");
    fs::write(&tmp, input_map::render(&file)).map_err(|e| e.to_string())?;
    fs::rename(&tmp, path).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_input_map(bindings: Bindings) -> Result<String, String> {
    let p = input_map_path();
    write_input_map(&p, bindings)?;
    Ok(s(&p))
}

/// "Restore defaults": the file goes (its other sections with it, kept in
/// input.toml.bak), so Play passes no PS3_INPUT_MAP again.
#[tauri::command]
fn reset_input_map() -> Result<(), String> {
    let p = input_map_path();
    if p.is_file() {
        fs::rename(&p, p.with_extension("toml.bak")).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// The names in the JSON array the screen probe prints.
fn parse_screens(json: &str) -> Vec<String> {
    serde_json::from_str::<Vec<String>>(json.trim()).unwrap_or_default()
}

/// The screens in the system's order (NSScreen.screens: the first has the
/// menu bar), by the names PS3_DISPLAY matches.
#[tauri::command]
async fn list_screens() -> Vec<String> {
    if !cfg!(target_os = "macos") {
        return Vec::new();
    }
    tauri::async_runtime::spawn_blocking(|| {
        command_stdout(Command::new("/usr/bin/osascript").args([
            "-l",
            "JavaScript",
            "-e",
            "ObjC.import('AppKit'); JSON.stringify($.NSScreen.screens.js.map(s => s.localizedName.js))",
        ]))
        .map(|s| parse_screens(&s))
        .unwrap_or_default()
    })
    .await
    .unwrap_or_default()
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModsView {
    dir: String,
    dump_dir: String,
    packs: Vec<mods::ModPack>,
}

/// The texture packs in <data>/mods (the folder is created, so "Open the
/// mods folder" always has somewhere to go).
#[tauri::command]
fn list_mods() -> ModsView {
    let dir = mods_dir();
    ModsView { packs: mods::list(&dir), dir: s(&dir), dump_dir: s(&mods_dump_dir()) }
}

#[tauri::command]
fn get_settings() -> Settings {
    load_settings_file()
}

/// The active profile is not the page's to change: `profile_set_active` is, so
/// a save while the game runs cannot move it.
#[tauri::command]
fn save_settings(app: AppHandle, mut settings: Settings) -> Result<(), String> {
    settings.active_profile = load_settings_file().active_profile;
    write_settings(&settings)?;
    sync_app_icon(&app);
    Ok(())
}

#[tauri::command]
async fn find_port_dirs() -> Vec<Builds> {
    tauri::async_runtime::spawn_blocking(find_port_dirs_now).await.unwrap_or_default()
}

#[tauri::command]
fn builds_at(path: String) -> Builds {
    resolve_builds(Path::new(path.trim()))
}

#[tauri::command]
async fn disc_status() -> DiscInfo {
    tauri::async_runtime::spawn_blocking(|| disc_info(&load_settings_file())).await.unwrap_or_default()
}

/// Attach the image and remember it (and a mount point of its own, if it has one).
#[tauri::command]
async fn mount_image(path: String) -> Result<DiscInfo, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = attach_image(Path::new(path.trim()))?;
        let mut st = load_settings_file();
        st.disc_image = path.trim().to_string();
        st.disc_path = if root == default_mount() { String::new() } else { s(&root) };
        write_settings(&st)?;
        Ok(disc_info(&st))
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Eject the disc when it is a mounted image (refused while the game runs).
#[tauri::command]
async fn eject_disc(state: State<'_, AppState>) -> Result<DiscInfo, String> {
    if state.game.lock().unwrap().is_some() || process_running(GAME_EXE) {
        return Err("the game is running: close it first".into());
    }
    tauri::async_runtime::spawn_blocking(|| {
        let st = load_settings_file();
        let root = find_disc(&st).ok_or("no disc mounted")?;
        if image_of(&root).is_none() {
            return Err(format!("{}: not a mounted disc image", root.display()));
        }
        let out = Command::new("/usr/bin/hdiutil").arg("detach").arg(&root).stdin(Stdio::null()).output().map_err(|e| format!("hdiutil: {e}"))?;
        if !out.status.success() {
            return Err(format!("hdiutil detach: {}", String::from_utf8_lossy(&out.stderr).trim()));
        }
        Ok(disc_info(&st))
    })
    .await
    .map_err(|e| e.to_string())?
}

// ---------------------------------------------------------------------------
// The Dock and Finder icons from the player's disc (app_icon.rs)
// ---------------------------------------------------------------------------

fn app_icon_cache() -> PathBuf {
    data_root().join(app_icon::CACHE_NAME)
}

fn composed_icon(s: &Settings) -> Option<PathBuf> {
    if !s.game_icon {
        return None;
    }
    app_icon::refresh(&app_icon_cache(), disc_art(s).0.as_deref())
}

fn sync_app_icon(app: &AppHandle) {
    if !cfg!(target_os = "macos") {
        return;
    }
    let app = app.clone();
    thread::spawn(move || {
        let icon = composed_icon(&load_settings_file());
        let key = app_icon::key(icon.as_deref());
        let state = app.state::<AppState>();
        let mut cur = state.dock_icon.lock().unwrap();
        if *cur != key {
            *cur = key;
            app_icon::apply_dock_icon(&app, icon);
        }
    });
}

#[tauri::command]
async fn finder_icon(app: AppHandle, set: bool) -> Result<bool, String> {
    if !cfg!(target_os = "macos") {
        return Err("the Finder icon is macOS only".into());
    }
    let bundle = app_icon::app_bundle().ok_or("the launcher is not running from an .app (development build)")?;
    let icon = if set {
        let st = load_settings_file();
        Some(app_icon::refresh(&app_icon_cache(), disc_art(&st).0.as_deref()).ok_or("no ICON0.PNG from your disc yet")?)
    } else {
        None
    };
    let (tx, rx) = std::sync::mpsc::channel();
    let b = bundle.clone();
    app.run_on_main_thread(move || {
        let _ = tx.send(app_icon::set_finder_icon(&b, icon.as_deref()));
    })
    .map_err(|e| e.to_string())?;
    rx.recv().map_err(|e| e.to_string())??;
    Ok(app_icon::has_finder_icon(&bundle))
}

#[tauri::command]
fn take_play_request(state: State<'_, AppState>) -> bool {
    let asked = std::mem::take(&mut *state.play_request.lock().unwrap());
    if asked {
        eprintln!("[launcher] --play: starting the game once the window is ready");
    }
    asked
}

/// The window's uncaught errors, on the launcher's stderr (development).
#[tauri::command]
fn frontend_log(message: String) {
    eprintln!("[launcher window] {}", message.chars().take(2000).collect::<String>());
}

#[tauri::command]
fn take_start_view(state: State<'_, AppState>) -> Option<String> {
    state.start_view.lock().unwrap().take()
}

/// Home > Status > "Play shortcut on the Desktop" (play_shortcut.rs).
#[tauri::command]
async fn create_play_shortcut(app: AppHandle) -> Result<String, String> {
    if !cfg!(target_os = "macos") {
        return Err("the Play shortcut is macOS only".into());
    }
    let bundle = app_icon::app_bundle().ok_or("the launcher is not running from an .app (development build)")?;
    let icns = play_shortcut::bundle_icns(&bundle);
    let path = play_shortcut::write(&home().join("Desktop"), &app.config().identifier, icns.as_deref())?;
    if let Some(icon) = composed_icon(&load_settings_file()) {
        let (tx, rx) = std::sync::mpsc::channel();
        let p = path.clone();
        app.run_on_main_thread(move || {
            let _ = tx.send(app_icon::set_finder_icon(&p, Some(&icon)));
        })
        .map_err(|e| e.to_string())?;
        if let Ok(Err(e)) = rx.recv() {
            eprintln!("[launcher] Play shortcut icon: {e}");
        }
    }
    Ok(s(&path))
}

// ---------------------------------------------------------------------------
// Add to Steam (steam.rs, steam_art.rs)
// ---------------------------------------------------------------------------

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SteamStatus {
    available: bool,
    installed: bool,
    running: bool,
    users: usize,
    added: usize,
}

fn steam_dir() -> PathBuf {
    data_root().join("steam")
}

fn steam_target() -> steam::Target {
    steam::Target::new(&play_shortcut::executable(&steam_dir().join(play_shortcut::NAME)))
}

fn steam_available() -> bool {
    cfg!(target_os = "macos") && app_icon::app_bundle().is_some()
}

fn steam_art(st: &Settings) -> Option<steam::Art> {
    let (icon0, pic1) = disc_art(st);
    let icon0 = app_icon::decode_png(&fs::read(icon0?).ok()?).ok()?;
    let pic1 = pic1.and_then(|p| fs::read(p).ok()).and_then(|b| app_icon::decode_png(&b).ok());
    let imgs = steam_art::draw(&icon0, pic1.as_ref());
    let enc = |i: &app_icon::Rgba| app_icon::encode_png(i).ok();
    Some([enc(&imgs.portrait)?, enc(&imgs.landscape)?, enc(&imgs.hero)?, enc(&imgs.icon)?])
}

#[tauri::command]
async fn steam_status() -> SteamStatus {
    tauri::async_runtime::spawn_blocking(|| {
        let users = steam::users(&steam::root(&home()));
        let t = steam_target();
        SteamStatus {
            available: steam_available(),
            installed: !users.is_empty(),
            running: steam::running(),
            users: users.len(),
            added: users.iter().filter(|u| steam::user_has(u, &t)).count(),
        }
    })
    .await
    .unwrap_or(SteamStatus { available: false, installed: false, running: false, users: 0, added: 0 })
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SteamAdded {
    users: usize,
    art: bool,
}

#[tauri::command]
async fn steam_add(app: AppHandle) -> Result<SteamAdded, String> {
    if !steam_available() {
        return Err("Add to Steam needs the packaged app on macOS".into());
    }
    let id = app.config().identifier.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let users = steam::users(&steam::root(&home()));
        if users.is_empty() {
            return Err("Steam is not installed here, or nobody has signed in to it yet".to_string());
        }
        if steam::running() {
            return Err("steam-running".to_string());
        }
        let icns = app_icon::app_bundle().and_then(|b| play_shortcut::bundle_icns(&b));
        fs::create_dir_all(steam_dir()).map_err(|e| e.to_string())?;
        play_shortcut::write_kind(&steam_dir(), &id, icns.as_deref(), play_shortcut::Kind::Steam)?;
        let art = steam_art(&load_settings_file());
        let t = steam_target();
        for u in &users {
            steam::add(u, &t, art.as_ref())?;
        }
        Ok(SteamAdded { users: users.len(), art: art.is_some() })
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn steam_remove(app: AppHandle) -> Result<usize, String> {
    let id = app.config().identifier.clone();
    tauri::async_runtime::spawn_blocking(move || {
        if steam::running() {
            return Err("steam-running".to_string());
        }
        let t = steam_target();
        let mut n = 0;
        for u in &steam::users(&steam::root(&home())) {
            n += steam::remove(u, &t)? as usize;
        }
        let bundle = steam_dir().join(play_shortcut::NAME);
        if play_shortcut::is_ours(&bundle, &id, play_shortcut::Kind::Steam) {
            fs::remove_dir_all(&bundle).map_err(|e| format!("{}: {e}", bundle.display()))?;
        }
        Ok(n)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn steam_quit() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(steam::quit).await.map_err(|e| e.to_string())?
}

// ---------------------------------------------------------------------------
// Requirements and the rebuild
// ---------------------------------------------------------------------------

/// One line of Advanced > Install / rebuild > "What this computer needs".
/// `level`: "ok", "warn", "fail", "info" (not a problem, only to know) or
/// "optional" (absent, and not needed). The window shows `key` (an i18n key
/// under `prereq.msg.`, with `vars`) and falls back to the English
/// `message`; `path` is shown on a line of its own, shortened, with the whole
/// path as a tooltip; `optional` marks something only some features need.
#[derive(Serialize, Clone, Debug, Default)]
#[serde(rename_all = "camelCase")]
pub struct CheckItem {
    level: String,
    name: String,
    message: String,
    key: String,
    vars: BTreeMap<String, String>,
    path: Option<String>,
    optional: bool,
}

impl CheckItem {
    fn new(level: &str, name: &str, key: &str, message: impl Into<String>) -> Self {
        CheckItem { level: level.into(), name: name.into(), key: key.into(), message: message.into(), ..Default::default() }
    }
    /// A check whose detail is only a path.
    fn at(level: &str, name: &str, path: &Path) -> Self {
        CheckItem::new(level, name, "", s(path)).path(path)
    }
    fn var(mut self, k: &str, v: impl ToString) -> Self {
        self.vars.insert(k.into(), v.to_string());
        self
    }
    fn path(mut self, p: &Path) -> Self {
        self.path = Some(s(p));
        self
    }
    fn optional(mut self) -> Self {
        self.optional = true;
        self
    }
}

#[derive(Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct Prereqs {
    supported: bool,
    clt: bool,
    checks: Vec<CheckItem>,
    ok: bool,
    disc: bool,
    builds_ok: bool,
    free_gb: Option<u64>,
}

fn free_gb(p: &Path) -> Option<u64> {
    let out = command_stdout(Command::new("/bin/df").arg("-k").arg(p))?;
    let kb: u64 = out.lines().nth(1)?.split_whitespace().nth(3)?.parse().ok()?;
    Some(kb / (1024 * 1024))
}

/// tools/build.sh refuses below this.
const BUILD_MIN_GB: u64 = 4;

/// The Python tools/env.sh uses (PES_VENV's), which also runs the launcher's
/// calls to tools/install_savedata.py and tools/pes2013_edit.py.
fn venv_python(root: &Path) -> PathBuf {
    std::env::var_os("PES_VENV")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("../deadpool-recomp/tools/.venv"))
        .join("bin/python")
}

fn toolkit_dir(root: &Path) -> PathBuf {
    std::env::var_os("PS3RECOMP_DIR").filter(|v| !v.is_empty()).map(PathBuf::from).unwrap_or_else(|| root.join("../ps3recomp-up-r8"))
}

#[tauri::command]
async fn check_prereqs() -> Prereqs {
    tauri::async_runtime::spawn_blocking(|| {
        let st = load_settings_file();
        let mut p = Prereqs { supported: host_supported(), clt: clt_installed(), ..Default::default() };
        let mut add = |c: CheckItem| p.checks.push(c);
        if !p.supported {
            return p;
        }
        let root = port_root(&st);
        let b = root.as_deref().map(resolve_builds);
        add(if p.clt {
            CheckItem::new("ok", "xcode-clt", "cltOk", "installed")
        } else {
            CheckItem::new("fail", "xcode-clt", "cltMissing", "not installed (Apple's installer: the compiler and git)")
        });
        for tool in ["cmake", "ninja"] {
            add(match find_in_path(tool) {
                Some(f) => CheckItem::at("ok", tool, &f),
                None => CheckItem::new("warn", tool, "toolMissing", "not found on PATH (needed only to rebuild)"),
            });
        }
        let disc = find_disc(&st);
        let iso = root.as_deref().and_then(port_iso);
        p.disc = disc.is_some() || iso.is_some();
        add(match (disc, iso) {
            (Some(d), _) => CheckItem::at("ok", "disc", &d),
            (None, Some(i)) => CheckItem::new("ok", "disc", "discIso", "not mounted: Play mounts this image read-only").path(&i),
            (None, None) => CheckItem::new("fail", "disc", "discMissing", "no disc mounted and no image in game_iso"),
        });
        if let Some(r) = &root {
            add(match data_pack(r) {
                Some(d) => CheckItem::at("ok", "datapack", &d),
                None => CheckItem::new("warn", "datapack", "packMissing", "no BLUS31029_DOWNLOAD: the game runs from the disc's data, without the data pack"),
            });
            let py = venv_python(r);
            add(if py.is_file() {
                CheckItem::at("ok", "venv", &py)
            } else {
                CheckItem::new("warn", "venv", "venvMissing", "not found: the rebuild and installing saves from a PS3 folder need it").path(&py)
            });
            let tk = toolkit_dir(r);
            add(if tk.is_dir() { CheckItem::at("ok", "toolkit", &tk) } else { CheckItem::new("warn", "toolkit", "toolkitMissing", "not found: the rebuild needs it").path(&tk) });
        }
        // only whether it is there: never its contents
        let keys = profiles::keys_file(&data_root());
        add(if keys.is_file() {
            CheckItem::new("ok", "savekeys", "keysOk", "there").optional()
        } else {
            CheckItem::new("info", "savekeys", "keysMissing", "not there: only installing saves from a PS3 folder needs it").optional()
        });
        let at = root.clone().filter(|r| r.exists()).unwrap_or_else(home);
        p.free_gb = free_gb(&at);
        if let Some(gb) = p.free_gb {
            add(if gb >= BUILD_MIN_GB {
                CheckItem::new("ok", "disk", "diskEnough", format!("{gb} GB free")).var("free", gb)
            } else {
                CheckItem::new("warn", "disk", "diskLow", format!("only {gb} GB free; tools/build.sh refuses below {BUILD_MIN_GB} GB")).var("free", gb).var("need", BUILD_MIN_GB)
            });
        }
        match &b {
            Some(b) => {
                p.builds_ok = b.ok;
                add(if b.ok {
                    CheckItem::at("ok", "builds", Path::new(&b.root))
                } else {
                    CheckItem::new("warn", "builds", "buildsMissing", format!("missing: {}", b.missing.join(", "))).var("missing", b.missing.join(", "))
                });
            }
            None => add(CheckItem::new("fail", "builds", "noPort", "no port folder found")),
        }
        p.ok = !p.checks.iter().any(|c| c.level == "fail");
        p
    })
    .await
    .unwrap_or_default()
}

#[tauri::command]
fn install_clt() -> Result<(), String> {
    Command::new("xcode-select")
        .arg("--install")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("xcode-select: {e}"))
}

/// Stream a child's stdout and stderr to the window as `<event>-line`, and
/// its exit code as `<event>-exit`; `slot` holds its pid while it runs.
fn stream_child(app: &AppHandle, mut child: std::process::Child, event: &'static str, which: fn(&AppState) -> &Mutex<Option<u32>>) {
    let (stdout, stderr) = (child.stdout.take().unwrap(), child.stderr.take().unwrap());
    let a1 = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let _ = a1.emit(&format!("{event}-line"), line);
        }
    });
    let a2 = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = a2.emit(&format!("{event}-line"), line);
        }
    });
    let a3 = app.clone();
    thread::spawn(move || {
        let code = child.wait().map(|s| s.code().unwrap_or(-1)).unwrap_or(-1);
        *which(&a3.state::<AppState>()).lock().unwrap() = None;
        let _ = a3.emit(&format!("{event}-exit"), code);
    });
}

/// tools/rebuild.sh's steps, in its order. Its build step goes through
/// tools/build.sh, whose guards (one build at a time, low memory, low disk,
/// BUILD_JOBS, a full rebuild only with BUILD_ALLOW_FULL=1) stay in charge.
const STEPS: &[&str] = &["decrypt", "analyse", "lift", "spu", "build"];

/// The rebuild, as a zsh script run in the port folder.
fn rebuild_script(steps: &[String]) -> String {
    let want: Vec<&str> = STEPS.iter().copied().filter(|s| steps.is_empty() || steps.iter().any(|x| x == s)).collect();
    format!("set -e\nexec tools/rebuild.sh {}\n", want.join(" "))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RebuildRequest {
    steps: Vec<String>,
    jobs: Option<u32>,
}

#[tauri::command]
fn start_rebuild(app: AppHandle, state: State<'_, AppState>, req: RebuildRequest) -> Result<(), String> {
    require_supported_host()?;
    if let Some(bad) = req.steps.iter().find(|s| !STEPS.contains(&s.as_str())) {
        return Err(format!("{bad}: not a step ({})", STEPS.join(" ")));
    }
    if state.game.lock().unwrap().is_some() {
        return Err("the game is running: close it before rebuilding".into());
    }
    let mut slot = state.rebuild.lock().unwrap();
    if slot.is_some() {
        return Err("a rebuild is already running".into());
    }
    let st = load_settings_file();
    let root = port_root(&st).ok_or("no port folder")?;
    if !root.join("tools/rebuild.sh").is_file() {
        return Err(format!("{}: no tools/rebuild.sh", root.display()));
    }
    let mut cmd = Command::new("/usr/bin/nice");
    cmd.args(["-n", "10", "/bin/zsh", "-c", &rebuild_script(&req.steps)])
        .current_dir(&root)
        .env("PATH", tool_path())
        .env("TERM", "dumb")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    // the lifter's; the compile stays at tools/build.sh's BUILD_JOBS
    if let Some(j) = req.jobs.filter(|j| *j > 0) {
        cmd.env("JOBS", j.to_string());
    }
    own_process_group(&mut cmd);
    let child = cmd.spawn().map_err(|e| format!("zsh: {e}"))?;
    *slot = Some(child.id());
    drop(slot);
    let _ = app.emit("rebuild-line", format!("$ cd {} && tools/rebuild.sh {}", root.display(), if req.steps.is_empty() { STEPS.join(" ") } else { req.steps.join(" ") }));
    stream_child(&app, child, "rebuild", |s| &s.rebuild);
    Ok(())
}

#[tauri::command]
fn cancel_rebuild(state: State<'_, AppState>) {
    if let Some(pid) = *state.rebuild.lock().unwrap() {
        kill_tree(pid, false);
    }
}

// ---------------------------------------------------------------------------
// Updates (update.rs)
// ---------------------------------------------------------------------------

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo {
    sources: update::Sources,
    /// The newest commit touching the port is newer than the EBOOT build.
    rebuild_needed: bool,
    built_at: u64,
    app: update::AppUpdate,
}

#[tauri::command]
async fn check_updates(online: bool) -> UpdateInfo {
    tauri::async_runtime::spawn_blocking(move || {
        let st = load_settings_file();
        let root = port_root(&st);
        let b = root.as_deref().map(resolve_builds);
        let sources = root.as_deref().map(|r| update::sources(r, online)).unwrap_or_default();
        let built_at = b.as_ref().map_or(0, |b| b.built_at);
        let rebuild_needed = built_at > 0 && sources.sources_time > built_at;
        let app = if online {
            update::check_app(env!("CARGO_PKG_VERSION"))
        } else {
            update::AppUpdate { current: env!("CARGO_PKG_VERSION").into(), ..Default::default() }
        };
        UpdateInfo { sources, rebuild_needed, built_at, app }
    })
    .await
    .unwrap_or(UpdateInfo { sources: Default::default(), rebuild_needed: false, built_at: 0, app: Default::default() })
}

/// "Get the new sources": git pull --ff-only in the port folder, streamed as
/// rebuild-line / rebuild-exit (the Install tab's log).
#[tauri::command]
fn pull_sources(app: AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    let mut slot = state.rebuild.lock().unwrap();
    if slot.is_some() {
        return Err("a rebuild is running".into());
    }
    let root = port_root(&load_settings_file()).ok_or("no port folder")?;
    let mut cmd = Command::new("git");
    cmd.arg("-C")
        .arg(&root)
        .args(["pull", "--ff-only"])
        .env("GIT_TERMINAL_PROMPT", "0")
        .env("PATH", tool_path())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    own_process_group(&mut cmd);
    let child = cmd.spawn().map_err(|e| format!("git: {e}"))?;
    *slot = Some(child.id());
    drop(slot);
    let _ = app.emit("rebuild-line", format!("$ git -C {} pull --ff-only", root.display()));
    stream_child(&app, child, "rebuild", |s| &s.rebuild);
    Ok(())
}

// ---------------------------------------------------------------------------
// Links, files, the log
// ---------------------------------------------------------------------------

const URL_ALLOWED: &[&str] = &["https://brew.sh/", "https://github.com/sp00nznet/ps3recomp"];

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if !URL_ALLOWED.iter().any(|p| url.starts_with(p)) || url.chars().any(|c| c.is_whitespace() || c == '"') {
        return Err(format!("{url}: not a link this app opens"));
    }
    Command::new("open").arg(&url).spawn().map(|_| ()).map_err(|e| e.to_string())
}

/// Show a folder or file in Finder (never opens an .app: that would run it).
#[tauri::command]
fn reveal(path: String) -> Result<(), String> {
    reveal_unix(PathBuf::from(&path))
}

/// What `open` gets for a reveal: `None` to open the folder itself, `Some("-R")`
/// to select the item in its folder. A path that does not exist is revealed as
/// its nearest existing ancestor, under the same rule, so a missing file inside
/// an app bundle can never make `open` launch that bundle.
fn reveal_target(p: &Path) -> Result<(PathBuf, bool), String> {
    if !p.is_absolute() {
        return Err(format!("{}: not an absolute path", p.display()));
    }
    let mut at = p.to_path_buf();
    while !at.exists() {
        match at.parent() {
            Some(up) => at = up.to_path_buf(),
            None => return Err(format!("{}: nothing to show", p.display())),
        }
    }
    let open_folder = at.is_dir() && at.extension().is_none_or(|e| e != "app");
    Ok((at, !open_folder))
}

fn reveal_unix(p: PathBuf) -> Result<(), String> {
    let (target, select) = reveal_target(&p)?;
    let mut cmd = Command::new("open");
    if select {
        cmd.arg("-R");
    }
    cmd.arg(&target).spawn().map(|_| ()).map_err(|e| e.to_string())
}

fn game_log_path(state: &State<'_, AppState>) -> PathBuf {
    state.last_log.lock().unwrap().clone().unwrap_or_else(|| data_root().join(LOG_NAME))
}

fn tail_text(data: &[u8], cut: bool) -> String {
    let start = if cut { data.iter().position(|&b| b == b'\n').map_or(0, |i| i + 1) } else { 0 };
    String::from_utf8_lossy(&data[start..]).into_owned()
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GameLog {
    path: String,
    exists: bool,
    size: u64,
    modified: u64,
    text: String,
    truncated: bool,
}

#[tauri::command]
fn read_game_log(state: State<'_, AppState>, max_bytes: Option<u64>) -> Result<GameLog, String> {
    let path = game_log_path(&state);
    let max = max_bytes.unwrap_or(512 * 1024).clamp(4 * 1024, 8 * 1024 * 1024);
    let mut out = GameLog { path: s(&path), exists: false, size: 0, modified: 0, text: String::new(), truncated: false };
    let Ok(mut f) = fs::File::open(&path) else { return Ok(out) };
    let meta = f.metadata().map_err(|e| e.to_string())?;
    out.exists = true;
    out.size = meta.len();
    out.modified = mtime(&path);
    out.truncated = meta.len() > max;
    if out.truncated {
        f.seek(SeekFrom::Start(meta.len() - max)).map_err(|e| e.to_string())?;
    }
    let mut buf = Vec::with_capacity(max.min(meta.len()) as usize);
    f.take(max).read_to_end(&mut buf).map_err(|e| e.to_string())?;
    out.text = tail_text(&buf, out.truncated);
    Ok(out)
}

#[tauri::command]
fn log_paths(state: State<'_, AppState>) -> BTreeMap<String, String> {
    let st = load_settings_file();
    let mut m = BTreeMap::new();
    m.insert("game".into(), s(&game_log_path(&state)));
    if let Ok(p) = active_profile(&st) {
        m.insert("saves".into(), p.savedata);
    }
    m.insert("data".into(), s(&data_root()));
    m.insert("sessions".into(), s(&sessions_dir()));
    m
}

// ---------------------------------------------------------------------------
// Shader cache
// ---------------------------------------------------------------------------

fn dir_usage(dir: &Path) -> (u64, u64) {
    let (mut bytes, mut files) = (0u64, 0u64);
    if let Ok(rd) = fs::read_dir(dir) {
        for e in rd.flatten() {
            match e.metadata() {
                Ok(m) if m.is_dir() => {
                    let (b, f) = dir_usage(&e.path());
                    bytes += b;
                    files += f;
                }
                Ok(m) => {
                    bytes += m.len();
                    files += 1;
                }
                Err(_) => {}
            }
        }
    }
    (bytes, files)
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ShaderCacheInfo {
    path: Option<String>,
    bytes: u64,
    files: u64,
}

fn shader_cache_info_now() -> ShaderCacheInfo {
    match msl_cache_dir(&load_settings_file()) {
        Some(d) => {
            let (bytes, files) = dir_usage(&d);
            ShaderCacheInfo { path: Some(s(&d)), bytes, files }
        }
        None => ShaderCacheInfo { path: None, bytes: 0, files: 0 },
    }
}

#[tauri::command]
fn shader_cache_info() -> ShaderCacheInfo {
    shader_cache_info_now()
}

/// The translated shaders (RSX_MSL_CACHE): regenerated as the game meets them.
#[tauri::command]
fn shader_cache_clear(state: State<'_, AppState>) -> Result<ShaderCacheInfo, String> {
    if state.game.lock().unwrap().is_some() || process_running(GAME_EXE) {
        return Err("the game is running: close it before clearing the shader cache".into());
    }
    if let Some(d) = msl_cache_dir(&load_settings_file()) {
        if d.exists() {
            fs::remove_dir_all(&d).map_err(|e| format!("{}: {e}", d.display()))?;
        }
    }
    Ok(shader_cache_info_now())
}

// ---------------------------------------------------------------------------
// Debug mode (report.rs)
// ---------------------------------------------------------------------------

fn session_event(dir: &Path, kind: &str, detail: &str) {
    let ms = now_ms();
    let _ = report::event(dir, ms, &utc_text(ms / 1000), kind, detail);
}

fn spawn_ticker(app: AppHandle, dir: PathBuf) {
    thread::spawn(move || loop {
        thread::sleep(std::time::Duration::from_secs(2));
        let live = matches!(app.state::<AppState>().report.lock().unwrap().as_ref(), Some((d, true)) if *d == dir);
        if !live {
            break;
        }
        session_event(&dir, "tick", "");
    });
}

fn session_exit(dir: &Path, status: Option<std::process::ExitStatus>, started: u64) {
    #[cfg(unix)]
    let signal = {
        use std::os::unix::process::ExitStatusExt;
        status.and_then(|s| s.signal())
    };
    #[cfg(not(unix))]
    let signal: Option<i32> = None;
    let code = status.and_then(|s| s.code());
    let detail = match (code, signal) {
        (Some(c), _) => format!("code={c}"),
        (None, Some(sig)) => format!("signal={sig}"),
        _ => "unknown".into(),
    };
    session_event(dir, "exit", &detail);
    let stopped = fs::read_to_string(dir.join(report::EVENTS)).is_ok_and(|t| t.contains("\tstop\t"));
    let crashed = signal.is_some() || code.is_some_and(|c| c != 0);
    if !crashed || stopped || !cfg!(target_os = "macos") {
        return;
    }
    let diag = home().join("Library/Logs/DiagnosticReports");
    for _ in 0..20 {
        if let Some(p) = report::find_crash_report(&diag, &[GAME_EXE], started) {
            if fs::copy(&p, dir.join(report::CRASH)).is_ok() {
                session_event(dir, "crash-report", &format!("file={}", p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()));
            }
            return;
        }
        thread::sleep(std::time::Duration::from_secs(1));
    }
}

fn command_line(program: &str, args: &[&str]) -> String {
    command_stdout(Command::new(program).args(args)).map(|s| s.trim().to_string()).unwrap_or_default()
}

/// UTC "YYYY-MM-DD HH:MM:SS".
fn utc_text(secs: u64) -> String {
    let st = saves::stamp(secs);
    format!("{}-{}-{} {}:{}:{}", &st[0..4], &st[4..6], &st[6..8], &st[9..11], &st[11..13], &st[13..15])
}

fn system_info(b: &Builds, disc: Option<&Path>, env: &[(String, String)], argv: &[String], now: u64) -> String {
    let mut t = String::new();
    let mut line = |k: &str, v: &str| {
        if !v.is_empty() {
            t.push_str(&format!("{k}: {v}\n"));
        }
    };
    line("report", &utc_text(now));
    line("launcher", env!("CARGO_PKG_VERSION"));
    line("os", &format!("{} {}", std::env::consts::OS, std::env::consts::ARCH));
    if cfg!(target_os = "macos") {
        line("macos", &format!("{} ({})", command_line("sw_vers", &["-productVersion"]), command_line("sw_vers", &["-buildVersion"])));
        line("model", &command_line("sysctl", &["-n", "hw.model"]));
        line("cpu", &command_line("sysctl", &["-n", "machdep.cpu.brand_string"]));
        let mem = command_line("sysctl", &["-n", "hw.memsize"]).parse::<u64>().unwrap_or(0);
        if mem > 0 {
            line("memory", &format!("{} GB", mem >> 30));
        }
        let gpus = command_stdout(Command::new("/usr/sbin/system_profiler").args(["SPDisplaysDataType", "-json"]))
            .and_then(|j| serde_json::from_str::<serde_json::Value>(&j).ok())
            .map(|v| {
                v["SPDisplaysDataType"]
                    .as_array()
                    .into_iter()
                    .flatten()
                    .filter_map(|g| g["sppci_model"].as_str().map(String::from))
                    .collect::<Vec<_>>()
                    .join(", ")
            })
            .unwrap_or_default();
        line("gpu", &gpus);
    }
    let v = disc.and_then(|d| read_sfo(&d.join("PS3_GAME/PARAM.SFO"))).unwrap_or_default();
    line("disc", &format!("{} {} {}", v.get("TITLE_ID").cloned().unwrap_or_default(), v.get("TITLE").cloned().unwrap_or_default(), v.get("APP_VER").cloned().unwrap_or_default()));
    line("port folder", &b.root);
    line("built", &utc_text(b.built_at));
    line("commit", &command_line("git", &["-C", &b.root, "rev-parse", "--short", "HEAD"]));
    t.push_str("\ncommand:\n  ");
    t.push_str(&argv.iter().map(|a| shell_quote(a)).collect::<Vec<_>>().join(" "));
    t.push_str("\n\nenvironment:\n");
    for (k, v) in env {
        t.push_str(&format!("  {k}={}\n", shell_quote(v)));
    }
    let home = s(&home());
    if home.len() > 1 {
        t = t.replace(&home, "~");
    }
    t
}

fn current_report(state: &State<'_, AppState>) -> Option<(PathBuf, bool)> {
    let r = state.report.lock().unwrap().clone();
    r.or_else(|| report::latest(&reports_dir()).map(|d| (d, false)))
}

#[tauri::command]
fn report_info(state: State<'_, AppState>) -> Option<report::Info> {
    current_report(&state).map(|(d, live)| report::info(&d, live))
}

#[tauri::command]
fn report_capture(state: State<'_, AppState>) -> Result<report::Info, String> {
    let game = state.game.lock().unwrap().is_some();
    match state.report.lock().unwrap().clone() {
        Some((d, true)) if game => {
            let ms = now_ms();
            report::capture(&d, &utc_text(ms / 1000), ms)?;
            Ok(report::info(&d, true))
        }
        _ => Err("the game was not started in debug mode".into()),
    }
}

fn report_dir_of(state: &State<'_, AppState>, id: Option<&str>) -> Result<(PathBuf, bool), String> {
    let cur = current_report(state);
    match id {
        Some(id) => {
            let d = report::by_id(&reports_dir(), id)?;
            let live = cur.is_some_and(|(c, live)| live && c == d);
            Ok((d, live))
        }
        None => cur.ok_or_else(|| "no report yet: start the game in debug mode first".into()),
    }
}

#[tauri::command]
async fn report_list(state: State<'_, AppState>) -> Result<Vec<report::Info>, String> {
    let cur = current_report(&state);
    tauri::async_runtime::spawn_blocking(move || {
        report::list(&reports_dir(), 40)
            .into_iter()
            .map(|d| {
                let live = cur.as_ref().is_some_and(|(c, live)| *live && *c == d);
                report::info(&d, live)
            })
            .collect()
    })
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
async fn report_triage(state: State<'_, AppState>, id: String) -> Result<report::Info, String> {
    let (dir, live) = report_dir_of(&state, Some(&id))?;
    tauri::async_runtime::spawn_blocking(move || {
        report::summarise(&dir)?;
        Ok(report::info(&dir, live))
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn report_zip(state: State<'_, AppState>, id: Option<String>, notes: Option<String>) -> Result<report::Info, String> {
    let (dir, live) = report_dir_of(&state, id.as_deref())?;
    tauri::async_runtime::spawn_blocking(move || {
        if let Some(n) = notes.as_deref().map(str::trim).filter(|n| !n.is_empty()) {
            fs::write(dir.join(report::NOTES), format!("{n}\n")).map_err(|e| e.to_string())?;
        }
        let _ = report::summarise(&dir);
        report::pack(&dir, &report::zip_path(&dir), &s(&home()))?;
        Ok(report::info(&dir, live))
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn report_delete(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let (_, live) = report_dir_of(&state, Some(&id))?;
    if live {
        return Err("that session is still running".into());
    }
    report::delete(&reports_dir(), &id)
}

// ---------------------------------------------------------------------------
// Saves (saves.rs)
// ---------------------------------------------------------------------------

fn game_busy(state: &AppState) -> bool {
    state.game.lock().unwrap().is_some() || process_running(GAME_EXE)
}

const BUSY: &str = "the game is running: close it before changing saves";

/// Run `f` on the active profile's folders. `write`: it changes saves there, so
/// a registered folder is refused. Never while the game or a profile job runs.
fn with_saves<T>(state: &State<'_, AppState>, write: bool, f: impl FnOnce(&saves::Locations) -> Result<T, String>) -> Result<T, String> {
    let game = state.game.lock().unwrap();
    if game.is_some() || process_running(GAME_EXE) {
        return Err(BUSY.into());
    }
    if state.profile_job.lock().unwrap().is_some() {
        return Err("an Option File profile is being changed: wait for it to finish".into());
    }
    let p = active_profile(&load_settings_file())?;
    if write && p.read_only {
        return Err(format!("{} is a registered folder: the launcher only reads it", p.name));
    }
    let r = f(&locations_of(&p));
    drop(game);
    r
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SavesOverview {
    port: Vec<Slot>,
    rpcs3: Vec<Slot>,
    rpcs3_users: Vec<String>,
    rpcs3_user: String,
    backups: Vec<BackupMeta>,
    /// The active profile's name, and that the launcher only reads it.
    profile: String,
    read_only: bool,
    port_dir: String,
    rpcs3_dir: String,
    backups_dir: String,
    game_running: bool,
    rpcs3_running: bool,
}

#[tauri::command]
async fn saves_overview(state: State<'_, AppState>, user: Option<String>) -> Result<SavesOverview, String> {
    let running = game_busy(&state);
    tauri::async_runtime::spawn_blocking(move || -> Result<SavesOverview, String> {
        let p = active_profile(&load_settings_file())?;
        let loc = locations_of(&p);
        let users = saves::rpcs3_users(&loc);
        let user = user.filter(|u| users.contains(u)).or_else(|| users.first().cloned()).unwrap_or_else(|| saves::PORT_USER.into());
        let mut port = saves::list_slots(&loc, Side::Port, "", true);
        let mut rpcs3 = if users.is_empty() { Vec::new() } else { saves::list_slots(&loc, Side::Rpcs3, &user, true) };
        saves::hash_twins(&mut port, &mut rpcs3);
        Ok(SavesOverview {
            port,
            rpcs3,
            rpcs3_users: users,
            rpcs3_user: user.clone(),
            backups: saves::list_backups(&loc),
            profile: p.name.clone(),
            read_only: p.read_only,
            port_dir: s(&loc.port_savedata),
            rpcs3_dir: s(&loc.rpcs3_savedata(&user)),
            backups_dir: s(&loc.backups),
            game_running: running,
            rpcs3_running: process_running("rpcs3") || process_running("RPCS3"),
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

// Backups only read the saves and write into the launcher's own folder, so they
// also work on a registered profile.
#[tauri::command]
async fn saves_backup(state: State<'_, AppState>, side: Side, user: String, slot: Option<String>) -> Result<Option<BackupMeta>, String> {
    with_saves(&state, false, |loc| {
        let one = slot.map(|s| vec![s]);
        saves::create_backup(loc, side, &user, one.as_deref(), "manual", now_secs())
    })
}

#[tauri::command]
async fn saves_restore(state: State<'_, AppState>, id: String, slot: Option<String>) -> Result<saves::Report, String> {
    with_saves(&state, true, |loc| saves::restore_backup(loc, &id, slot.as_deref(), now_secs()))
}

#[tauri::command]
async fn saves_delete_backup(state: State<'_, AppState>, id: String) -> Result<(), String> {
    with_saves(&state, false, |loc| saves::delete_backup(loc, &id))
}

#[tauri::command]
async fn saves_copy(state: State<'_, AppState>, from: Side, to: Side, user: String, slot: String) -> Result<saves::Report, String> {
    with_saves(&state, true, |loc| saves::copy_slot(loc, from, to, &user, &slot, now_secs()))
}

#[tauri::command]
async fn saves_delete_slot(state: State<'_, AppState>, side: Side, user: String, slot: String) -> Result<BackupMeta, String> {
    with_saves(&state, true, |loc| saves::delete_slot(loc, side, &user, &slot, now_secs()))
}

fn zip_dest(dest: &str) -> Result<PathBuf, String> {
    let mut dest = PathBuf::from(dest.trim());
    if dest.as_os_str().is_empty() {
        return Err("no file chosen".into());
    }
    if !dest.extension().is_some_and(|e| e.eq_ignore_ascii_case("zip")) {
        dest.as_mut_os_string().push(".zip");
    }
    Ok(dest)
}

#[tauri::command]
async fn saves_export_zip(state: State<'_, AppState>, slots: Option<Vec<String>>, dest: String) -> Result<String, String> {
    let dest = zip_dest(&dest)?;
    with_saves(&state, false, |loc| saves::export_zip(loc, slots.as_deref(), &dest, now_secs()))?;
    Ok(s(&dest))
}

#[tauri::command]
async fn saves_import_zip(state: State<'_, AppState>, path: String) -> Result<saves::Report, String> {
    with_saves(&state, true, |loc| saves::import_zip(loc, Path::new(path.trim()), now_secs()))
}

/// The game's trophies with the active profile's unlocks (Game page). Reads
/// the disc, so it needs it mounted; run.sh or the Disc section does that.
#[tauri::command]
async fn list_trophies() -> Result<trophies::TrophyList, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let st = load_settings_file();
        let disc = find_disc(&st).ok_or("no disc mounted")?;
        let p = active_profile(&st)?;
        let lang = if st.game_lang.is_empty() { "pt" } else { st.game_lang.as_str() };
        trophies::list(&disc, Path::new(&p.root), lang, true)
    })
    .await
    .map_err(|e| e.to_string())?
}

// ---------------------------------------------------------------------------
// Option File profiles (profiles.rs)
// ---------------------------------------------------------------------------

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileView {
    #[serde(flatten)]
    profile: profiles::Profile,
    #[serde(flatten)]
    usage: profiles::Usage,
    /// What tools/pes2013_edit.py read from BLUS31029EEDIT.
    edit: Option<profiles::EditCounts>,
    /// Why it could not.
    edit_error: Option<String>,
    active: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfilesView {
    profiles: Vec<ProfileView>,
    active: String,
    /// Refuses switching and changes: the game is running.
    game_running: bool,
    /// A create or delete is under way.
    busy: bool,
    /// The key file tools/install_savedata.py takes exists (never read here).
    keys: bool,
    /// The Python that runs the tools exists.
    python: bool,
}

/// Ask tools/pes2013_edit.py, once per file version. It prints the whole decoded
/// table, of which only the counts are kept; under nice, since it is only for a
/// list on a page.
fn edit_counts(root: &Path, data_bin: &Path, cache: &Mutex<BTreeMap<(String, u64, u64), Result<profiles::EditCounts, String>>>) -> Result<profiles::EditCounts, String> {
    let meta = fs::metadata(data_bin).map_err(|e| e.to_string())?;
    let key = (s(data_bin), meta.len(), mtime_of(&meta));
    if let Some(r) = cache.lock().unwrap().get(&key) {
        return r.clone();
    }
    let r = run_edit_tool(&venv_python(root), &root.join("tools/pes2013_edit.py"), data_bin);
    cache.lock().unwrap().insert(key, r.clone());
    r
}

fn run_edit_tool(python: &Path, tool: &Path, data_bin: &Path) -> Result<profiles::EditCounts, String> {
    let py = if python.is_file() { python.to_path_buf() } else { PathBuf::from("/usr/bin/python3") };
    let out = Command::new("/usr/bin/nice")
        .args(["-n", "10"])
        .arg(&py)
        .arg("-I")
        .arg(tool)
        .arg(data_bin)
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("{}: {e}", py.display()))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).trim().lines().last().unwrap_or("the tool failed").to_string());
    }
    profiles::parse_edit_json(&String::from_utf8_lossy(&out.stdout))
}

#[tauri::command]
async fn profiles_list(app: AppHandle) -> Result<ProfilesView, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let st = load_settings_file();
        let store = profile_store(&st);
        let state = app.state::<AppState>();
        let root = port_root(&st);
        let active = profiles::resolve(&store, &st.active_profile).map(|p| p.id).unwrap_or_else(|_| st.active_profile.clone());
        let list = profiles::list(&store)
            .into_iter()
            .map(|p| {
                let usage = profiles::usage(Path::new(&p.savedata));
                let (mut edit, mut edit_error) = (None, None);
                if usage.has_edit {
                    if let Some(r) = &root {
                        match edit_counts(r, &Path::new(&p.savedata).join(saves::EDIT_SLOT).join("DATA.BIN"), &state.edit_cache) {
                            Ok(c) => edit = Some(c),
                            Err(e) => edit_error = Some(e),
                        }
                    }
                }
                ProfileView { active: p.id == active, profile: p, usage, edit, edit_error }
            })
            .collect();
        let busy = state.profile_job.lock().unwrap().is_some();
        let view = ProfilesView {
            profiles: list,
            active,
            game_running: game_busy(&state),
            busy,
            keys: profiles::keys_file(&data_root()).is_file(),
            python: root.as_deref().is_some_and(|r| venv_python(r).is_file()),
        };
        view
    })
    .await
    .map_err(|e| e.to_string())
}

/// Claim the profile job, refused while the game runs or another job does. The
/// game's lock is held across both checks, as Play holds it across its own.
fn begin_profile_job(state: &AppState, pid: u32) -> Result<(), String> {
    let game = state.game.lock().unwrap();
    if game.is_some() || process_running(GAME_EXE) {
        return Err(BUSY.into());
    }
    let mut job = state.profile_job.lock().unwrap();
    if job.is_some() {
        return Err("an Option File profile is already being changed".into());
    }
    *job = Some(pid);
    Ok(())
}

fn end_profile_job(app: &AppHandle) {
    *app.state::<AppState>().profile_job.lock().unwrap() = None;
}

/// Run `f` as the profile job, off the window's thread.
async fn profile_job<T: Send + 'static>(app: AppHandle, f: impl FnOnce() -> Result<T, String> + Send + 'static) -> Result<T, String> {
    begin_profile_job(&app.state::<AppState>(), 0)?;
    let a = app.clone();
    let r = tauri::async_runtime::spawn_blocking(f).await.map_err(|e| e.to_string());
    end_profile_job(&a);
    r?
}

#[tauri::command]
fn profile_set_active(state: State<'_, AppState>, id: String) -> Result<(), String> {
    if game_busy(&state) {
        return Err("the game is running: close it before switching the Option File".into());
    }
    if state.profile_job.lock().unwrap().is_some() {
        return Err("an Option File profile is being changed: wait for it to finish".into());
    }
    let mut st = load_settings_file();
    let p = profiles::resolve(&profile_store(&st), &id)?;
    st.active_profile = p.id;
    write_settings(&st)
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileCreate {
    name: String,
    /// "empty", "copy" (of the profile `from`) or "zip" (the file `path`).
    kind: String,
    from: Option<String>,
    path: Option<String>,
}

/// The free space a copy of `bytes` should leave.
fn check_room(data: &Path, bytes: u64) -> Result<(), String> {
    const SPARE_GB: u64 = 1;
    let at = if data.exists() { data.to_path_buf() } else { home() };
    if let Some(gb) = free_gb(&at) {
        if gb < (bytes >> 30) + SPARE_GB + 1 {
            return Err(format!("only {gb} GB free on this disk"));
        }
    }
    Ok(())
}

#[tauri::command]
async fn profile_create(app: AppHandle, req: ProfileCreate) -> Result<profiles::Profile, String> {
    profile_job(app, move || {
        let st = load_settings_file();
        let store = profile_store(&st);
        match req.kind.as_str() {
            "empty" => profiles::create_empty(&store, &req.name),
            "copy" => {
                let from = profiles::resolve(&store, req.from.as_deref().unwrap_or(""))?;
                check_room(&store.data, profiles::usage(Path::new(&from.savedata)).bytes)?;
                profiles::create_copy(&store, &req.name, &from)
            }
            "zip" => {
                let zip = PathBuf::from(req.path.as_deref().unwrap_or("").trim());
                check_room(&store.data, fs::metadata(&zip).map_err(|e| format!("{}: {e}", zip.display()))?.len() * 2)?;
                profiles::create_from_zip(&store, &req.name, &zip, now_secs())
            }
            k => Err(format!("{k}: not a way to create a profile")),
        }
    })
    .await
}

/// A new profile from a folder of PS3 saves: tools/install_savedata.py into the
/// new profile's stage, never into an existing one (it replaces saves). Streamed
/// as profile-line / profile-exit, which carries the outcome.
#[tauri::command]
fn profile_install(app: AppHandle, state: State<'_, AppState>, name: String, path: String) -> Result<(), String> {
    let st = load_settings_file();
    let store = profile_store(&st);
    let root = port_root(&st).ok_or("no port folder")?;
    let src = profiles::saves_source(Path::new(path.trim()))?;
    let keys = profiles::keys_file(&store.data);
    if !keys.is_file() {
        return Err(format!("no key file at {}", keys.display()));
    }
    let tool = root.join("tools/install_savedata.py");
    if !tool.is_file() {
        return Err(format!("{}: not there", tool.display()));
    }
    let python = venv_python(&root);
    if !python.is_file() {
        return Err(format!("{}: not there", python.display()));
    }
    check_room(&store.data, profiles::usage(&src).bytes)?;
    begin_profile_job(&state, 0)?;
    let started = (|| -> Result<(String, std::process::Child), String> {
        let (name, dst) = profiles::prepare_install(&store, &name)?;
        let mut cmd = Command::new(&python);
        cmd.arg("-I")
            .arg(&tool)
            .arg(&src)
            .arg(&dst)
            .arg("--keys")
            .arg(&keys)
            .current_dir(&store.data)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        own_process_group(&mut cmd);
        let child = cmd.spawn().map_err(|e| format!("{}: {e}", python.display()));
        match child {
            Ok(c) => Ok((name, c)),
            Err(e) => {
                profiles::abandon(&store, &name);
                Err(e)
            }
        }
    })();
    let (name, mut child) = match started {
        Ok(v) => v,
        Err(e) => {
            end_profile_job(&app);
            return Err(e);
        }
    };
    *state.profile_job.lock().unwrap() = Some(child.id());
    let _ = app.emit("profile-line", format!("$ tools/install_savedata.py {} <{name}> --keys <data>/keys/savedata_keys.txt", src.display()));
    let (stdout, stderr) = (child.stdout.take().unwrap(), child.stderr.take().unwrap());
    let a1 = app.clone();
    let out = thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let _ = a1.emit("profile-line", line);
        }
    });
    let a2 = app.clone();
    let err = thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = a2.emit("profile-line", line);
        }
    });
    thread::spawn(move || {
        let code = child.wait().map(|s| s.code().unwrap_or(-1)).unwrap_or(-1);
        let _ = (out.join(), err.join());
        let outcome = if code == 0 {
            profiles::commit(&store, &name).map(|p| p.id)
        } else {
            profiles::abandon(&store, &name);
            Err(format!("code {code}"))
        };
        end_profile_job(&app);
        let _ = app.emit("profile-exit", serde_json::json!({ "ok": outcome.is_ok(), "id": outcome.as_ref().ok(), "error": outcome.as_ref().err() }));
    });
    Ok(())
}

/// Stop the install (its own process group, by pid); nothing is left of it.
#[tauri::command]
fn profile_cancel(state: State<'_, AppState>) {
    if let Some(pid) = state.profile_job.lock().unwrap().filter(|p| *p > 0) {
        kill_tree(pid, false);
    }
}

#[tauri::command]
fn profile_register(state: State<'_, AppState>, name: String, path: String) -> Result<profiles::Profile, String> {
    begin_profile_job(&state, 0)?;
    let r = profiles::register_external(&profile_store(&load_settings_file()), &name, Path::new(path.trim()));
    *state.profile_job.lock().unwrap() = None;
    r
}

/// Delete a local profile, or forget a registered one. `confirm` repeats its
/// name. Deleting the active one makes padrão active.
#[tauri::command]
async fn profile_delete(app: AppHandle, id: String, confirm: String) -> Result<(), String> {
    profile_job(app, move || {
        let mut st = load_settings_file();
        let store = profile_store(&st);
        let was_active = profiles::resolve(&store, &st.active_profile).is_ok_and(|p| p.id == id);
        profiles::delete(&store, &id, &confirm)?;
        if was_active {
            st.active_profile = profiles::BUILTIN_ID.into();
            write_settings(&st)?;
        }
        Ok(())
    })
    .await
}

#[tauri::command]
async fn profile_export_zip(app: AppHandle, id: String, dest: String) -> Result<String, String> {
    profile_job(app, move || {
        let p = profiles::resolve(&profile_store(&load_settings_file()), &id)?;
        let dest = zip_dest(&dest)?;
        saves::export_zip(&locations_of(&p), None, &dest, now_secs())?;
        Ok(s(&dest))
    })
    .await
}

/// Import a .zip into a profile the launcher owns: never padrão from this page
/// (the saves manager asks with the profile named), never a registered folder.
#[tauri::command]
async fn profile_import_zip(app: AppHandle, id: String, path: String) -> Result<saves::Report, String> {
    profile_job(app, move || {
        let p = profiles::resolve(&profile_store(&load_settings_file()), &id)?;
        if p.kind != profiles::Kind::Local {
            return Err(format!("{}: only a profile made here can take an import", p.name));
        }
        saves::import_zip(&locations_of(&p), Path::new(path.trim()), now_secs())
    })
    .await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::default())
        .setup(|app| {
            sync_app_icon(app.handle());
            let args: Vec<String> = std::env::args().collect();
            let st = app.state::<AppState>();
            *st.play_request.lock().unwrap() = play_shortcut::requested(args.iter().cloned());
            *st.exit_with_game.lock().unwrap() = play_shortcut::exit_requested(&args);
            *st.start_view.lock().unwrap() = play_shortcut::start_view(&args);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            get_input_map,
            save_input_map,
            reset_input_map,
            list_screens,
            list_mods,
            get_status,
            find_port_dirs,
            builds_at,
            disc_status,
            mount_image,
            eject_disc,
            check_updates,
            pull_sources,
            check_prereqs,
            install_clt,
            open_url,
            start_rebuild,
            cancel_rebuild,
            launch_preview,
            play,
            stop_game,
            reveal,
            log_paths,
            read_game_log,
            shader_cache_info,
            shader_cache_clear,
            saves_overview,
            saves_backup,
            saves_restore,
            saves_delete_backup,
            saves_copy,
            saves_delete_slot,
            saves_export_zip,
            saves_import_zip,
            list_trophies,
            profiles_list,
            profile_set_active,
            profile_create,
            profile_install,
            profile_cancel,
            profile_register,
            profile_delete,
            profile_export_zip,
            profile_import_zip,
            report_info,
            report_list,
            report_triage,
            report_capture,
            report_zip,
            report_delete,
            finder_icon,
            take_play_request,
            take_start_view,
            frontend_log,
            create_play_shortcut,
            steam_status,
            steam_add,
            steam_remove,
            steam_quit
        ])
        .build(tauri::generate_context!())
        .expect("error while running the launcher")
        .run(|app, ev| {
            // Quitting stops a rebuild or a saves install (their own process
            // groups, by pid). The game keeps running, as it would from a shell.
            if let tauri::RunEvent::Exit = ev {
                let st = app.state::<AppState>();
                if let Some(pid) = *st.rebuild.lock().unwrap() {
                    kill_tree(pid, false);
                }
                let job = st.profile_job.lock().unwrap().filter(|p| *p > 0);
                if let Some(pid) = job {
                    kill_tree(pid, false);
                }
            }
        });
}

#[cfg(test)]
mod tests;

