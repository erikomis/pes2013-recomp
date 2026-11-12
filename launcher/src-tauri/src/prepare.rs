//! The launcher without its window, for programs that start it
//! (RecompLauncher, see `recomplauncher.json` at the repository's top and the
//! launcher README, "RecompLauncher"):
//!
//! - `--prepare --game <copy> [--update <01.04 .pkg>] [--pack <Data Pack 6>]`:
//!   what Home > Install the game does, without a window: the copy checked
//!   (the BLUS31029 disc image, or a folder with PS3_GAME/) and remembered as
//!   the disc, the 01.04 update, the key file (never given here: the one the
//!   window's Install card remembers, or `<data>/keys/self_keys.txt`), Apple's
//!   Command Line Tools and Homebrew's formulas (looked at, never installed),
//!   then install.zsh (sources, toolkit, venv, game, decrypt, analyse, lift,
//!   SPU, build). It prints `progress <0..1> <text>` lines, the scripts' output
//!   as plain lines, and exits with one of the codes in `Exit`, 0 only when the
//!   game's build is there afterwards.
//! - `--play` with `RECOMPLAUNCHER=1`: the game started at once (the same Play
//!   as the window's button: the profile, the disc, the settings, the save
//!   backup, last.log), no window; the launcher's process becomes the game's
//!   (exec), so its exit code and its lifetime are the game's. `--game <copy>`
//!   uses and remembers that disc.
//!
//! Both decide in `run()` before any window or Tauri event loop exists. The
//! install itself is the window's (install_job, spawn_install, finish_install
//! in lib.rs); only where its output goes differs (OutputSink).

use crate::*;
use std::collections::VecDeque;
use std::io::Write;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc};
use std::time::Instant;

/// The headless prepare's and `--play`'s exit codes (as recomplauncher.json's
/// exit_codes says them to the player).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Exit {
    /// Prepare: the game is built. Play: the game was quit normally.
    Ok,
    /// No copy given, not found, not the US disc BLUS31029; the 01.04 update
    /// missing or not BLUS31029's; a data pack that is not this game's.
    Copy,
    /// Something the player has to do first: Apple's Command Line Tools (their
    /// installer is opened), Homebrew's formulas, the key file, or not a Mac.
    NeedsPlayer,
    /// A download the install makes (the toolkit, Python packages) failed: the
    /// connection.
    Sources,
    /// The install or the build failed (install.log has why), or too little
    /// free space.
    Build,
    /// Another prepare, or this game's build, is running.
    Running,
    /// Play: the game is not built yet.
    NotBuilt,
    /// The launcher failed on its own (its settings, starting a program).
    Failed,
}

impl Exit {
    #[cfg(test)]
    pub const ALL: [Exit; 8] = [Exit::Ok, Exit::Copy, Exit::NeedsPlayer, Exit::Sources, Exit::Build, Exit::Running, Exit::NotBuilt, Exit::Failed];

    pub fn code(self) -> i32 {
        match self {
            Exit::Ok => 0,
            Exit::Copy => 40,
            Exit::NeedsPlayer => 41,
            Exit::Sources => 42,
            Exit::Build => 43,
            Exit::Running => 44,
            Exit::NotBuilt => 45,
            Exit::Failed => 46,
        }
    }

    /// What the player is told (recomplauncher.json's exit_codes; "ok" for a
    /// normal end).
    pub fn says(self) -> &'static str {
        match self {
            Exit::Ok => "ok",
            Exit::Copy => "Your copy isn't the one this port reads: it needs your own PES 2013 US disc, BLUS31029, as a decrypted disc image (.iso) or a folder with PS3_GAME and PS3_DISC.SFB, and its 01.04 update (.pkg). Pick them again on the game's page.",
            Exit::NeedsPlayer => "Your Mac needs something first: Apple's Command Line Tools (their installer opened: finish it), Homebrew's cmake, ninja, sdl2 and python@3.12, or the key file that decrypts the game (never shipped: add it once in the PES 2013 Launcher window, Home > Install the game). Then set the game up again.",
            Exit::Sources => "Couldn't download what the build needs (the toolkit from GitHub or its Python packages). Check the internet connection and set the game up again.",
            Exit::Build => "Building the game failed. Check there are about 10 GB free, then set it up again: it continues where it stopped. install.log in the logs folder says why.",
            Exit::Running => "PES 2013 is already running, or another setup of it is. Close it or wait for it, then try again.",
            Exit::NotBuilt => "The game isn't built yet. Set it up again on the game's page (the first time takes 30 to 60 minutes).",
            Exit::Failed => "The PES 2013 launcher couldn't start it. Open the launcher itself to see why.",
        }
    }
}

// ---------------------------------------------------------------------------
// The command line
// ---------------------------------------------------------------------------

pub const PREPARE_ARG: &str = "--prepare";
pub const GAME_ARG: &str = "--game";
pub const UPDATE_ARG: &str = "--update";
pub const PACK_ARG: &str = "--pack";

/// What `--prepare` was given.
#[derive(Debug, Default, PartialEq)]
pub struct PrepareArgs {
    pub game: Option<PathBuf>,
    /// The 01.04 update's .pkg.
    pub update: Option<PathBuf>,
    /// The Data Pack 6: its folder (with USRDIR) or its .pkg.
    pub pack: Option<PathBuf>,
    /// Arguments that came with a placeholder left in (`{input:...}`, from a
    /// launcher that does not fill it in): taken as not given.
    pub unfilled: Vec<&'static str>,
}

#[derive(Debug, PartialEq)]
pub enum Mode {
    /// `--prepare [--game <copy>] [--update <pkg>] [--pack <pack>]`: the
    /// headless install.
    Prepare(PrepareArgs),
    /// `--play [--game <copy>]` started by RecompLauncher: the game, no window.
    PlayDirect { game: Option<PathBuf> },
    /// The window (with `--play`: Play once it is up).
    Window { game: Option<PathBuf> },
}

/// `<name> <value>` or `<name>=<value>` (argv, program first); an empty value
/// counts as none.
fn value_arg(args: &[String], name: &str) -> Option<String> {
    let eq = format!("{name}=");
    let mut it = args.iter().skip(1);
    while let Some(a) = it.next() {
        if let Some(v) = a.strip_prefix(&eq) {
            return Some(v.to_string()).filter(|v| !v.is_empty());
        }
        if a == name {
            return it.next().filter(|v| !v.is_empty()).cloned();
        }
    }
    None
}

/// A path argument, unless it still holds a launcher's placeholder.
fn path_arg(args: &[String], name: &'static str, unfilled: &mut Vec<&'static str>) -> Option<PathBuf> {
    let v = value_arg(args, name)?;
    if v.contains("{input:") || v.contains("{game}") {
        unfilled.push(name);
        return None;
    }
    Some(PathBuf::from(v))
}

pub fn game_arg(args: &[String]) -> Option<PathBuf> {
    path_arg(args, GAME_ARG, &mut Vec::new())
}

/// What the command line (argv, program first) asks for; `recomplauncher`:
/// RECOMPLAUNCHER=1 is set (under_recomplauncher).
pub fn mode(args: &[String], recomplauncher: bool) -> Mode {
    if args.iter().skip(1).any(|a| a == PREPARE_ARG) {
        let mut unfilled = Vec::new();
        let game = path_arg(args, GAME_ARG, &mut unfilled);
        let update = path_arg(args, UPDATE_ARG, &mut unfilled);
        let pack = path_arg(args, PACK_ARG, &mut unfilled);
        Mode::Prepare(PrepareArgs { game, update, pack, unfilled })
    } else if recomplauncher && play_shortcut::requested(args.iter().cloned()) {
        Mode::PlayDirect { game: game_arg(args) }
    } else {
        Mode::Window { game: game_arg(args) }
    }
}

/// RecompLauncher sets RECOMPLAUNCHER=1 for every game it starts.
pub fn under_recomplauncher() -> bool {
    std::env::var("RECOMPLAUNCHER").is_ok_and(|v| v.trim() == "1")
}

// ---------------------------------------------------------------------------
// The player's copy
// ---------------------------------------------------------------------------

#[derive(Debug, PartialEq)]
pub enum GameCopy {
    /// A folder with PS3_GAME/ (its root).
    Folder(PathBuf),
    /// A disc image (.iso).
    Image(PathBuf),
}

/// A disc ID as written in PS3_DISC.SFB or PARAM.SFO, compared without the
/// dash: "BLUS-31029" and "BLUS31029" are the same.
fn id_key(v: &str) -> String {
    v.chars().filter(|c| c.is_ascii_alphanumeric()).collect::<String>().to_ascii_uppercase()
}

/// The TITLE_ID in a PS3_DISC.SFB: ".SFB", then 0x20-byte entries from 0x20
/// (a 16-byte name, the value's offset and length, big-endian).
pub fn sfb_title_id(d: &[u8]) -> Option<String> {
    if d.len() < 0x40 || &d[..4] != b".SFB" {
        return None;
    }
    let be = |o: usize| u32::from_be_bytes([d[o], d[o + 1], d[o + 2], d[o + 3]]) as usize;
    let mut at = 0x20;
    while at + 0x20 <= d.len().min(0x200) {
        let name = &d[at..at + 16];
        if name.split(|&b| b == 0).next() == Some(b"TITLE_ID") {
            let (off, len) = (be(at + 16), be(at + 20));
            let v = d.get(off..off.checked_add(len)?)?;
            return Some(String::from_utf8_lossy(v.split(|&b| b == 0).next().unwrap_or(&[])).trim().to_string());
        }
        at += 0x20;
    }
    None
}

/// A file or folder in an ISO 9660 directory.
struct IsoEntry {
    name: String,
    lba: u64,
    size: u64,
    dir: bool,
}

fn read_exact_at(f: &mut fs::File, at: u64, len: usize) -> Option<Vec<u8>> {
    let mut buf = vec![0u8; len];
    f.seek(SeekFrom::Start(at)).ok()?;
    f.read_exact(&mut buf).ok()?;
    Some(buf)
}

/// An ISO 9660 image's block size and root directory (its primary volume
/// descriptor, sector 16), when it is one.
fn iso_root(f: &mut fs::File) -> Option<(u64, u64, u64)> {
    let pvd = read_exact_at(f, 16 * 2048, 2048)?;
    if pvd[0] != 1 || &pvd[1..6] != b"CD001" {
        return None;
    }
    let le32 = |o: usize| u32::from_le_bytes([pvd[o], pvd[o + 1], pvd[o + 2], pvd[o + 3]]) as u64;
    let block = u16::from_le_bytes([pvd[128], pvd[129]]) as u64;
    let block = if block == 0 { 2048 } else { block };
    Some((block, le32(156 + 2), le32(156 + 10)))
}

/// The entries of an ISO 9660 directory (at most 1 MiB of it is read).
fn iso_dir(f: &mut fs::File, block: u64, lba: u64, size: u64) -> Vec<IsoEntry> {
    let Some(d) = read_exact_at(f, lba * block, size.min(1 << 20) as usize) else { return Vec::new() };
    let mut out = Vec::new();
    let mut at = 0usize;
    while at + 33 < d.len() {
        let len = d[at] as usize;
        if len == 0 {
            // records never cross a block: the rest of this one is padding
            at = (at / block as usize + 1) * block as usize;
            continue;
        }
        if len < 34 || at + len > d.len() {
            break;
        }
        let r = &d[at..at + len];
        let le32 = |o: usize| u32::from_le_bytes([r[o], r[o + 1], r[o + 2], r[o + 3]]) as u64;
        let name_len = r[32] as usize;
        let raw = &r[33..(33 + name_len).min(len)];
        if raw != [0] && raw != [1] {
            let name = String::from_utf8_lossy(raw);
            let name = name.split(';').next().unwrap_or("").trim_end_matches('.').to_string();
            out.push(IsoEntry { name, lba: le32(2), size: le32(10), dir: r[25] & 2 != 0 });
        }
        at += len;
    }
    out
}

/// A disc image's TITLE_ID (from PS3_DISC.SFB) and PARAM.SFO version, read
/// from its ISO 9660 file system without mounting it. Errors are the player's.
fn image_ids(p: &Path) -> Result<(String, String), String> {
    let mut f = fs::File::open(p).map_err(|e| format!("Couldn't read {}: {e}", p.display()))?;
    let (block, lba, size) = iso_root(&mut f).ok_or_else(|| format!("{} isn't a disc image (.iso): pick your PES 2013 disc image or its folder.", p.display()))?;
    let root = iso_dir(&mut f, block, lba, size);
    let find = |es: &[IsoEntry], n: &str| es.iter().position(|e| e.name.eq_ignore_ascii_case(n));
    let sfb = find(&root, "PS3_DISC.SFB").filter(|&i| !root[i].dir).ok_or_else(|| format!("{} isn't a PS3 game disc (it has no PS3_DISC.SFB).", p.display()))?;
    let e = &root[sfb];
    let id = read_exact_at(&mut f, e.lba * block, e.size.min(64 * 1024) as usize).and_then(|d| sfb_title_id(&d)).unwrap_or_default();
    // PS3_GAME/PARAM.SFO's version, when it can be read
    let version = find(&root, "PS3_GAME")
        .filter(|&i| root[i].dir)
        .map(|i| iso_dir(&mut f, block, root[i].lba, root[i].size))
        .and_then(|g| g.into_iter().find(|e| e.name.eq_ignore_ascii_case("PARAM.SFO") && !e.dir))
        .and_then(|e| read_exact_at(&mut f, e.lba * block, e.size.min(64 * 1024) as usize))
        .map(|d| saves::sfo_values(&d))
        .and_then(|v| v.get("VERSION").or(v.get("APP_VER")).cloned())
        .unwrap_or_default();
    Ok((id, version))
}

fn wrong_disc(id: &str) -> String {
    if id.is_empty() {
        "That disc's ID can't be read: this port needs your PES 2013 US disc, BLUS31029.".into()
    } else {
        format!("That disc is {id}, not PES 2013's US disc BLUS31029 (other regions don't work yet).")
    }
}

/// Whether `p` is the player's BLUS31029 disc: a disc image whose PS3_DISC.SFB
/// says BLUS-31029, or a folder with PS3_GAME/ whose PARAM.SFO says BLUS31029
/// (and whose PS3_DISC.SFB, when there, agrees) and that has the EBOOT. Reads
/// only; returns the copy and its version (may be empty). The error is said to
/// the player.
pub fn check_copy(p: &Path) -> Result<(GameCopy, String), String> {
    if !p.exists() {
        return Err(format!("{} isn't there: pick your PES 2013 disc image (.iso) or its folder again.", p.display()));
    }
    if p.is_dir() {
        let root = disc_root_of(p).ok_or_else(|| format!("{} has no PS3_GAME folder: pick the folder that holds PS3_GAME and PS3_DISC.SFB, or the disc image (.iso).", p.display()))?;
        let sfo = saves::read_sfo(&root.join("PS3_GAME/PARAM.SFO")).ok_or("Its PS3_GAME/PARAM.SFO can't be read: the copy may be incomplete.")?;
        let id = sfo.get("TITLE_ID").cloned().unwrap_or_default();
        if id_key(&id) != TITLE_ID {
            return Err(wrong_disc(&id));
        }
        if let Ok(d) = fs::read(root.join("PS3_DISC.SFB")) {
            let sfb = sfb_title_id(&d).unwrap_or_default();
            if id_key(&sfb) != TITLE_ID {
                return Err(wrong_disc(&sfb));
            }
        }
        if !root.join("PS3_GAME/USRDIR/EBOOT.BIN").is_file() {
            return Err("That folder has no PS3_GAME/USRDIR/EBOOT.BIN: the copy is incomplete.".into());
        }
        let version = sfo.get("VERSION").or(sfo.get("APP_VER")).cloned().unwrap_or_default();
        return Ok((GameCopy::Folder(root), version));
    }
    let (id, version) = image_ids(p)?;
    if id_key(&id) != TITLE_ID {
        return Err(wrong_disc(&id));
    }
    Ok((GameCopy::Image(p.to_path_buf()), version))
}

/// `--game` with the window: check it and remember it as the disc before the
/// window opens. Returns whether `--play` may go ahead (no `--game`, or a good
/// one).
pub fn window_game(game: Option<&Path>) -> bool {
    let Some(g) = game else { return true };
    match check_copy(g).and_then(|_| remember_disc(g)) {
        Ok(at) => {
            eprintln!("[launcher] --game: the disc is {}", at.display());
            true
        }
        Err(e) => {
            eprintln!("[launcher] --game {}: {e} (--play is not started)", g.display());
            false
        }
    }
}

// ---------------------------------------------------------------------------
// The other files an install takes
// ---------------------------------------------------------------------------

/// Where `--prepare` finds the key file when no window gave one: the data
/// folder's `keys/`, beside the Option File's savedata_keys.txt. Only whether
/// it is there is looked at; its path goes to tools/decrypt_self.py.
pub fn keys_fallback(data: &Path) -> PathBuf {
    data.join("keys/self_keys.txt")
}

fn a_file(p: &str) -> Option<PathBuf> {
    let p = Path::new(p.trim());
    (p.is_absolute() && p.is_file()).then(|| p.to_path_buf())
}

/// The files install.zsh takes for this copy: the image (none for a folder,
/// which Play passes as PES_MOUNT), the update from `--update` or the one the
/// window remembered, the key file the window remembered or `keys_fallback`,
/// the data pack from `--pack` or the window's, and never an Option File (the
/// window's Option File page does those). `have_elf`, `have_bin`: the install
/// decrypted / extracted the EBOOT already, so the key file / the update are
/// not needed any more. Checked as install::check does; nothing is opened but
/// the package headers. The error is said to the player.
pub fn install_inputs(copy: &GameCopy, a: &PrepareArgs, remembered: &install::Inputs, data: &Path, have_elf: bool, have_bin: bool) -> Result<install::Inputs, (Exit, String)> {
    let s = |p: &Path| p.to_string_lossy().into_owned();
    let iso = match copy {
        GameCopy::Image(p) => s(p),
        GameCopy::Folder(_) => String::new(),
    };
    let pkg = match &a.update {
        Some(p) => s(p),
        None => a_file(&remembered.pkg).map(|p| s(&p)).unwrap_or_default(),
    };
    if pkg.is_empty() && !have_bin {
        return Err((Exit::Copy, "The 01.04 update wasn't given: pick your PES 2013 update .pkg (BLUS31029, version 01.04) on the game's page.".into()));
    }
    let keys = a_file(&remembered.keys).or_else(|| Some(keys_fallback(data)).filter(|p| p.is_file())).map(|p| s(&p)).unwrap_or_default();
    if keys.is_empty() && !have_elf {
        return Err((
            Exit::NeedsPlayer,
            format!(
                "The key file that decrypts the game isn't set (it never comes with the port): open the PES 2013 Launcher, choose it once under Home > Install the game, or put it at {}, then set the game up again.",
                keys_fallback(data).display()
            ),
        ));
    }
    let pack = match &a.pack {
        Some(p) => s(p),
        None => Some(PathBuf::from(remembered.pack.trim())).filter(|p| p.is_absolute() && p.exists()).map(|p| s(&p)).unwrap_or_default(),
    };
    let inputs = install::Inputs { iso, pkg, keys, pack, option_file: String::new(), save_keys: String::new() };
    install::check_inputs(&inputs, have_elf, have_bin, matches!(copy, GameCopy::Image(_))).map_err(|e| (Exit::Copy, e))?;
    Ok(inputs)
}

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

/// One output line, ignoring a closed stdout (the program that started us may
/// have stopped reading).
fn say(line: &str) {
    let mut o = std::io::stdout().lock();
    let _ = writeln!(o, "{line}");
    let _ = o.flush();
}

/// `progress <fraction> <text>` (RecompLauncher's prepare contract): the
/// fraction from 0 to 1 with three decimals, the text on one line.
pub fn progress_line(f: f64, text: &str) -> String {
    let text: String = text.split_whitespace().collect::<Vec<_>>().join(" ");
    format!("progress {:.3} {text}", f.clamp(0.0, 1.0))
}

/// A terminal's colour and bold escapes (\x1b[...m) taken out.
pub fn strip_esc(line: &str) -> String {
    let mut out = String::with_capacity(line.len());
    let mut it = line.chars().peekable();
    while let Some(c) = it.next() {
        if c == '\x1b' && it.peek() == Some(&'[') {
            it.next();
            for c in it.by_ref() {
                if c.is_ascii_alphabetic() {
                    break;
                }
            }
            continue;
        }
        out.push(c);
    }
    out
}

/// A script's output line as it is printed: without escapes, and indented when
/// it would read as a progress line itself.
pub fn log_line(raw: &str) -> String {
    let l = strip_esc(raw);
    if l.starts_with("progress") {
        format!("  {l}")
    } else {
        l
    }
}

/// The progress lines printed: the fraction never goes back, and a line is
/// printed only when the text changes or the fraction moves by half a percent.
#[derive(Default)]
pub struct Reporter {
    last: f64,
    printed: f64,
    text: String,
    any: bool,
}

impl Reporter {
    pub fn update(&mut self, f: f64, text: &str) -> Option<String> {
        let f = f.clamp(0.0, 1.0).max(self.last);
        self.last = f;
        if self.any && text == self.text && f < self.printed + 0.005 && !(f >= 1.0 && self.printed < 1.0) {
            return None;
        }
        self.any = true;
        self.printed = f;
        self.text = text.to_string();
        Some(progress_line(f, text))
    }

    /// The same, always printed (a step's end or a failure's reason).
    pub fn force(&mut self, f: f64, text: &str) -> String {
        self.any = false;
        self.update(f, text).unwrap_or_default()
    }

    fn say(&mut self, f: f64, text: &str) {
        if let Some(l) = self.update(f, text) {
            say(&l);
        }
    }

    fn fail(&mut self, text: &str) {
        let l = self.force(self.last, text);
        say(&l);
    }

    #[cfg(test)]
    pub fn last(&self) -> f64 {
        self.last
    }
}

/// The install's steps, as the window's progress bar has them for Install
/// the game without an Option File (src/progress.ts: the same ids and
/// weights, a step's rough share of a full install).
pub const STEP_IDS: [&str; 9] = ["sources", "toolkit", "venv", "game", "decrypt", "analyse", "lift", "spu", "build"];
const WEIGHT: [f64; 9] = [1.0, 2.0, 3.0, 2.0, 1.0, 6.0, 30.0, 6.0, 46.0];

#[derive(Clone, Copy, Debug, PartialEq)]
enum StepState {
    Pending,
    Running,
    Done,
    Skipped,
    Error,
}

#[derive(Clone, Copy)]
struct Step {
    state: StepState,
    start: f64,
    sub: Option<f64>,
}

/// The install's progress from the scripts' "==> <step>" lines, as
/// src/progress.ts reads them: the next step ends the one before, steps gone
/// past without a line count as skipped, "==> [k/n]" moves the running step
/// along, "==> done" ends the one running. Times are in seconds from any start.
pub struct StepTracker {
    steps: [Step; 9],
}

impl Default for StepTracker {
    fn default() -> Self {
        StepTracker { steps: [Step { state: StepState::Pending, start: 0.0, sub: None }; 9] }
    }
}

impl StepTracker {
    fn current(&mut self) -> Option<&mut Step> {
        self.steps.iter_mut().find(|s| s.state == StepState::Running)
    }

    fn close(&mut self, state: StepState) {
        if let Some(c) = self.current() {
            c.state = state;
        }
    }

    pub fn feed(&mut self, raw: &str, t: f64) {
        let line = strip_esc(raw);
        // "==>", then at least one space
        let Some(rest) = line.strip_prefix("==>").filter(|r| r.starts_with(char::is_whitespace)) else { return };
        let rest = rest.trim_start();
        if let Some(k) = rest.strip_prefix('[').and_then(|r| r.split_once(']')).and_then(|(kn, _)| kn.split_once('/')) {
            if let (Ok(k), Ok(n)) = (k.0.trim().parse::<f64>(), k.1.trim().parse::<f64>()) {
                if let Some(c) = self.current() {
                    c.sub = Some(((k - 1.0) / n.max(1.0)).clamp(0.0, 1.0));
                }
            }
            return;
        }
        let word: String = rest.chars().take_while(|c| c.is_ascii_lowercase()).collect();
        if word.is_empty() {
            return;
        }
        if word == "done" {
            self.close(StepState::Done);
            return;
        }
        let Some(i) = STEP_IDS.iter().position(|s| *s == word) else { return };
        self.close(StepState::Done);
        for s in &mut self.steps[..i] {
            if s.state == StepState::Pending {
                s.state = StepState::Skipped;
            }
        }
        self.steps[i] = Step { state: StepState::Running, start: t, sub: None };
    }

    /// The run ended: the running step done or failed; on success what never
    /// ran counts as skipped.
    pub fn finish(&mut self, ok: bool) {
        self.close(if ok { StepState::Done } else { StepState::Error });
        if ok {
            for s in &mut self.steps {
                if s.state == StepState::Pending {
                    s.state = StepState::Skipped;
                }
            }
        }
    }

    /// The share of the install done at `t`: a running step counts as far as it
    /// says, or as half done after two minutes and at most 90 %.
    pub fn fraction(&self, t: f64) -> f64 {
        let total: f64 = WEIGHT.iter().sum();
        let mut done = 0.0;
        for (s, w) in self.steps.iter().zip(WEIGHT) {
            match s.state {
                StepState::Done | StepState::Skipped => done += w,
                StepState::Running => {
                    let el = (t - s.start).max(0.0);
                    done += w * s.sub.unwrap_or(0.0).max((el / (el + 120.0)).min(0.9));
                }
                _ => {}
            }
        }
        done / total
    }

    /// The step running, or the one that failed (the last one that ran, when
    /// a step had already ended with "==> done").
    pub fn stage(&self) -> Option<&'static str> {
        self.steps
            .iter()
            .position(|s| matches!(s.state, StepState::Running | StepState::Error))
            .or_else(|| self.steps.iter().rposition(|s| s.state == StepState::Done))
            .map(|i| STEP_IDS[i])
    }
}

/// A step's text under the progress bar.
pub fn stage_text(id: Option<&str>) -> &'static str {
    match id {
        Some("sources") => "Copying the port's sources",
        Some("toolkit") => "Downloading the toolkit",
        Some("venv") => "Setting up Python",
        Some("game") => "Unpacking the 01.04 update",
        Some("decrypt") => "Decrypting the game's EBOOT",
        Some("analyse") => "Analysing the game's code",
        Some("lift") => "Translating the game's code (a long step)",
        Some("spu") => "Translating the SPU programs",
        Some("build") => "Compiling the game (the longest step)",
        _ => "Starting the build",
    }
}

/// The share of the bar before the install starts (the files, the tools) and
/// where the install's share ends.
const INSTALL_FROM: f64 = 0.04;
const INSTALL_TO: f64 = 0.99;

pub fn overall(install_fraction: f64) -> f64 {
    INSTALL_FROM + (INSTALL_TO - INSTALL_FROM) * install_fraction.clamp(0.0, 1.0)
}

/// Why the install failed, from the step it stopped at and its last lines (as
/// the window's installError tells them apart).
pub fn classify(stage: Option<&str>, tail: &[String]) -> Exit {
    let text = tail.join("\n").to_ascii_lowercase();
    let has = |n: &[&str]| n.iter().any(|x| text.contains(x));
    if has(&["build: refused: held by"]) {
        Exit::Running
    } else if has(&["could not resolve host", "failed to connect", "unable to access", "connection timed out", "network is unreachable", "could not install the python packages"]) {
        Exit::Sources
    } else if has(&["no space left on device"]) {
        Exit::Build
    } else if stage == Some("game") {
        // the update .pkg, the disc image or the data pack the player gave
        Exit::Copy
    } else if stage == Some("decrypt") {
        // the key file does not decrypt this EBOOT
        Exit::NeedsPlayer
    } else {
        Exit::Build
    }
}

/// The install's output, for the headless prepare: every line printed
/// (log_line), the steps followed, progress lines as the bar moves, the last
/// lines kept for classify, and the exit code sent on.
struct Headless {
    st: Mutex<HeadlessState>,
    done: Mutex<Option<mpsc::Sender<i32>>>,
    t0: Instant,
}

struct HeadlessState {
    steps: StepTracker,
    rep: Reporter,
    tail: VecDeque<String>,
    errors: Vec<String>,
}

impl Headless {
    fn tick(&self) {
        let t = self.t0.elapsed().as_secs_f64();
        let mut st = self.st.lock().unwrap();
        let f = overall(st.steps.fraction(t));
        let text = stage_text(st.steps.stage());
        if let Some(l) = st.rep.update(f, text) {
            say(&l);
        }
    }
}

impl OutputSink for Headless {
    fn line(&self, raw: &str) {
        let line = log_line(raw);
        say(&line);
        {
            let mut st = self.st.lock().unwrap();
            st.steps.feed(&line, self.t0.elapsed().as_secs_f64());
            if let Some(e) = line.strip_prefix("ERROR:") {
                st.errors.push(e.trim().to_string());
            }
            st.tail.push_back(line);
            if st.tail.len() > 400 {
                st.tail.pop_front();
            }
        }
        self.tick();
    }
    fn exit(&self, code: i32) {
        if let Some(tx) = self.done.lock().unwrap().take() {
            let _ = tx.send(code);
        }
    }
}

/// One headless prepare at a time: an exclusive lock on <data>/prepare.lock,
/// held while the returned file is open (the system drops it when the process
/// ends, however it ends). None: another one holds it.
fn take_lock() -> Result<Option<fs::File>, String> {
    let data = data_root();
    fs::create_dir_all(&data).map_err(|e| format!("{}: {e}", data.display()))?;
    let p = data.join("prepare.lock");
    let f = fs::OpenOptions::new().create(true).truncate(false).write(true).open(&p).map_err(|e| format!("{}: {e}", p.display()))?;
    match f.try_lock() {
        Ok(()) => Ok(Some(f)),
        Err(fs::TryLockError::WouldBlock) => Ok(None),
        Err(fs::TryLockError::Error(e)) => Err(format!("{}: {e}", p.display())),
    }
}

/// The command lines this game's build runs with: tools/run.sh ends in
/// `exec ... <port>/build/BLUS31029/PES2013Recomp <port>/game/EBOOT.elf`. Not
/// the name alone: other ports' games on this Mac are all called *Recomp.
pub fn running_pattern() -> String {
    format!("{TITLE_ID}/{GAME_EXE}( |$)")
}

/// This game's build is running (started anywhere: the window, a terminal,
/// RecompLauncher). Only looked at, never signalled.
fn game_running() -> bool {
    if cfg!(windows) {
        return process_running(GAME_EXE);
    }
    Command::new("pgrep").args(["-f", &running_pattern()]).stdout(Stdio::null()).stderr(Stdio::null()).status().is_ok_and(|s| s.success())
}

/// The resource folder of the .app this program runs from
/// (Contents/MacOS/<program> -> Contents/Resources), where the bundled port
/// sources are.
fn own_resources() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.canonicalize().unwrap_or(exe);
    Some(exe.parent()?.parent()?.join("Resources"))
}

/// `--prepare`'s process: run_prepare, then on a failure what its exit code
/// means to the player as the last line. Returns the exit code.
pub fn prepare_main(a: &PrepareArgs) -> i32 {
    let e = run_prepare(a);
    if e != Exit::Ok {
        say(&format!("Exit code {}: {}", e.code(), e.says()));
    }
    e.code()
}

/// `--prepare --game <copy> ...`: see the module's comment. Prints progress and
/// log lines on stdout; never opens a window.
pub fn run_prepare(a: &PrepareArgs) -> Exit {
    let mut rep = Reporter::default();
    rep.say(0.0, "Checking your copy of the game");
    if !cfg!(target_os = "macos") || !host_supported() {
        rep.fail("This port builds and runs on a Mac (Apple silicon) only.");
        return Exit::NeedsPlayer;
    }
    for name in &a.unfilled {
        say(&format!("{name}: the launcher left its placeholder in, so it counts as not given."));
    }
    let Some(game) = a.game.as_deref() else {
        rep.fail("No copy of the game given: --game <your PES 2013 BLUS31029 disc image or folder>.");
        return Exit::Copy;
    };
    // read only so far: nothing is written before the files are known good
    let (copy, version) = match check_copy(game) {
        Ok(c) => c,
        Err(e) => {
            rep.fail(&e);
            return Exit::Copy;
        }
    };
    say(&format!("Your copy: {} (BLUS31029{})", game.display(), if version.is_empty() { String::new() } else { format!(", version {version}") }));
    let l = install_layout();
    let game_dir = l.port().join("game");
    let st = load_settings_file();
    let inputs = match install_inputs(&copy, a, &st.install, &l.data, game_dir.join("EBOOT.elf").is_file(), game_dir.join("EBOOT.BIN").is_file()) {
        Ok(i) => i,
        Err((e, why)) => {
            rep.fail(&why);
            return e;
        }
    };
    if !inputs.pkg.is_empty() {
        say(&format!("The update: {}", inputs.pkg));
    }
    if !inputs.pack.is_empty() {
        say(&format!("The data pack: {}", inputs.pack));
    }

    let _lock = match take_lock() {
        Ok(Some(f)) => f,
        Ok(None) => {
            rep.fail("Another setup of PES 2013 is already running.");
            return Exit::Running;
        }
        Err(e) => {
            rep.fail(&format!("Couldn't write the launcher's folder: {e}"));
            return Exit::Failed;
        }
    };
    if game_running() {
        rep.fail("PES 2013 is running: close it, then set it up again.");
        return Exit::Running;
    }

    // Apple's Command Line Tools: their installer needs the player
    rep.say(0.01, "Checking Apple's Command Line Tools");
    if !clt_installed() {
        let opened = open_clt_installer().is_ok();
        rep.fail(if opened {
            "Apple's Command Line Tools are needed: finish their installer (it just opened), then set the game up again."
        } else {
            "Apple's Command Line Tools are needed: run xcode-select --install in Terminal, then set the game up again."
        });
        return Exit::NeedsPlayer;
    }
    // Homebrew's formulas: installed only with the player's yes (the window asks)
    rep.say(0.02, "Checking the build tools");
    let missing = install::brew_missing(&brew_prefix());
    if !missing.is_empty() {
        let cmd = format!("brew install {}", missing.join(" "));
        rep.fail(&if find_brew().is_some() {
            format!("The build needs {}: run `{cmd}` in Terminal (or Install the game in the PES 2013 Launcher window, which offers it), then set the game up again.", missing.join(", "))
        } else {
            format!("The build needs Homebrew (brew.sh) and then `{cmd}`; then set the game up again.")
        });
        return Exit::NeedsPlayer;
    }
    let Some(stage) = stage_in(own_resources()) else {
        rep.fail("This launcher carries no port sources (a development build: run scripts/stage_port.py).");
        return Exit::Failed;
    };

    // the disc and the files, remembered as the window's own (Game > Disc, the
    // Install card); the key file and the Option File stay as the window set them
    rep.say(0.03, "Remembering your copy");
    let remembered = remember_disc(game).and_then(|at| {
        let mut st = load_settings_file();
        if let GameCopy::Image(p) = &copy {
            st.install.iso = s(p);
        }
        if !inputs.pkg.is_empty() {
            st.install.pkg = inputs.pkg.clone();
        }
        if !inputs.pack.is_empty() {
            st.install.pack = inputs.pack.clone();
        }
        write_settings(&st).map(|_| at)
    });
    match remembered {
        Ok(at) => say(&format!("The disc: {}", at.display())),
        Err(e) => {
            rep.fail(&format!("Couldn't remember the disc in the launcher's settings: {e}"));
            return Exit::Failed;
        }
    }

    // the window's Install the game, with its output here
    rep.say(INSTALL_FROM, stage_text(None));
    let job = match install_job(&inputs, &stage, matches!(copy, GameCopy::Image(_))) {
        Ok(j) => j,
        Err(InstallRefusal::Clt) | Err(InstallRefusal::Brew) => {
            rep.fail("Apple's Command Line Tools or Homebrew's build tools are missing: set the game up again once they are installed.");
            return Exit::NeedsPlayer;
        }
        Err(InstallRefusal::Disk(gb)) => {
            rep.fail(&format!("Only {gb} GB free: the install needs about {} GB.", install::NEED_GB));
            return Exit::Build;
        }
        Err(InstallRefusal::Inputs(e)) => {
            rep.fail(&e);
            return Exit::Copy;
        }
        Err(InstallRefusal::Other(e)) => {
            rep.fail(&e);
            return Exit::Failed;
        }
    };
    let (tx, rx) = mpsc::channel();
    let sink = Arc::new(Headless {
        st: Mutex::new(HeadlessState { steps: StepTracker::default(), rep, tail: VecDeque::new(), errors: Vec::new() }),
        done: Mutex::new(Some(tx)),
        t0: Instant::now(),
    });
    let ended = match spawn_install(job, sink.clone()) {
        Ok((_, t)) => t,
        Err(e) => {
            let mut st = sink.st.lock().unwrap();
            st.rep.fail(&format!("Couldn't start the install: {e}"));
            return Exit::Failed;
        }
    };
    // the bar moves inside a long step too (the lift, the compile)
    let stop = Arc::new(AtomicBool::new(false));
    let ticker = {
        let (sink, stop) = (sink.clone(), stop.clone());
        thread::spawn(move || {
            while !stop.load(Ordering::SeqCst) {
                for _ in 0..50 {
                    if stop.load(Ordering::SeqCst) {
                        return;
                    }
                    thread::sleep(std::time::Duration::from_millis(100));
                }
                sink.tick();
            }
        })
    };
    let code = rx.recv().unwrap_or(-1);
    let _ = ended.join();
    stop.store(true, Ordering::SeqCst);
    let _ = ticker.join();

    let mut st = sink.st.lock().unwrap();
    let ok = code == 0;
    st.steps.finish(ok);
    if !ok {
        let stage = st.steps.stage();
        let tail: Vec<String> = st.tail.iter().cloned().collect();
        let exit = classify(stage, &tail);
        let why = st.errors.last().cloned().unwrap_or_else(|| format!("{} failed (code {code}).", stage_text(stage)));
        st.rep.fail(&why);
        say(&format!("The install's log: {}", l.log().display()));
        return exit;
    }
    // Play uses the installed port from now on, as after the window's install
    if let Err(e) = finish_install(false) {
        st.rep.fail(&format!("The install ended, but {e}"));
        return Exit::Build;
    }
    let line = st.rep.force(1.0, "Ready to play");
    say(&line);
    Exit::Ok
}

/// `--play` under RecompLauncher: the copy given with `--game` remembered, then
/// the window's Play (play_run: the profile, the disc, the settings, the save
/// backup), and the launcher's process replaced by the game's (exec), its
/// output in last.log (the previous one moved to logs/). Returns an exit code
/// only when the game could not start.
pub fn play_direct(game: Option<&Path>) -> i32 {
    let refuse = |e: Exit, why: &str| {
        eprintln!("[launcher] --play: {why}");
        e.code()
    };
    if let Some(g) = game {
        if let Err(e) = check_copy(g) {
            return refuse(Exit::Copy, &e);
        }
        if let Err(e) = remember_disc(g) {
            return refuse(Exit::Failed, &e);
        }
    }
    if let Err(e) = require_supported_host() {
        return refuse(Exit::NeedsPlayer, &e);
    }
    if game_running() {
        return refuse(Exit::Running, "the game is already running");
    }
    let s = load_settings_file();
    // caffeinate is started beside the game rather than in front of it, so the
    // process that is exec'd is tools/run.sh, which execs the game itself
    let mut no_caffeinate = s.clone();
    no_caffeinate.keep_awake = false;
    let run = match play_run(&no_caffeinate, &Mutex::new(FeatureCache::default()), false) {
        Ok(r) => r,
        Err(PlayRefusal::NotBuilt(e)) => return refuse(Exit::NotBuilt, &e),
        Err(PlayRefusal::Disc(e)) => return refuse(Exit::Copy, &e),
        Err(PlayRefusal::Other(e)) => return refuse(Exit::Failed, &e),
    };
    if let Some(e) = &run.backup_error {
        eprintln!("[launcher] --play: the save backup failed: {e}");
    }
    let (log_path, _) = session_log(None);
    let (out, err) = match fs::File::create(&log_path).and_then(|f| f.try_clone().map(|g| (f, g))) {
        Ok(f) => f,
        Err(e) => return refuse(Exit::Failed, &format!("{}: {e}", log_path.display())),
    };
    let mut cmd = game_command(&run.argv, &run.env, &run.root);
    cmd.stdout(out).stderr(err);
    eprintln!("[launcher] --play: starting the game (profile {}), log {}", run.profile, log_path.display());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        if s.keep_awake && Path::new("/usr/bin/caffeinate").is_file() {
            // waits for this process id, which the game keeps
            let _ = Command::new("/bin/sh")
                .args(["-c", "/usr/bin/caffeinate -i -w \"$1\" >/dev/null 2>&1 &", "sh", &std::process::id().to_string()])
                .stdin(Stdio::null())
                .status();
        }
        let e = cmd.exec();
        refuse(Exit::Failed, &format!("{}: {e}", run.argv[0]))
    }
    #[cfg(not(unix))]
    {
        match cmd.status() {
            Ok(st) => st.code().unwrap_or(Exit::Failed.code()),
            Err(e) => refuse(Exit::Failed, &format!("{}: {e}", run.argv[0])),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("pes-prep-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d.canonicalize().unwrap()
    }

    fn args(v: &[&str]) -> Vec<String> {
        std::iter::once("launcher").chain(v.iter().copied()).map(String::from).collect()
    }

    fn profile() -> serde_json::Value {
        serde_json::from_str(include_str!("../../../recomplauncher.json")).unwrap()
    }

    #[test]
    fn command_line() {
        let prep = |game: Option<&str>, update: Option<&str>, pack: Option<&str>, unfilled: Vec<&'static str>| {
            Mode::Prepare(PrepareArgs { game: game.map(PathBuf::from), update: update.map(PathBuf::from), pack: pack.map(PathBuf::from), unfilled })
        };
        assert_eq!(mode(&args(&["--prepare", "--game", "/x/pes.iso"]), false), prep(Some("/x/pes.iso"), None, None, vec![]));
        assert_eq!(mode(&args(&["--game=/x/disc", "--prepare", "--update=/x/u.pkg", "--pack", "/x/dp6"]), true), prep(Some("/x/disc"), Some("/x/u.pkg"), Some("/x/dp6"), vec![]));
        assert_eq!(mode(&args(&["--prepare"]), false), prep(None, None, None, vec![]));
        assert_eq!(mode(&args(&["--prepare", "--game"]), false), prep(None, None, None, vec![]));
        assert_eq!(mode(&args(&["--prepare", "--game", "", "--update="]), false), prep(None, None, None, vec![]));
        // a placeholder the starting launcher did not fill in is not a path
        assert_eq!(mode(&args(&["--prepare", "--game", "/a b/p.iso", "--update={input:update}", "--pack={input:pack}"]), true), prep(Some("/a b/p.iso"), None, None, vec![UPDATE_ARG, PACK_ARG]));
        // --play opens the window, unless RecompLauncher started it
        assert_eq!(mode(&args(&["--play"]), false), Mode::Window { game: None });
        assert_eq!(mode(&args(&["--play", "--game", "/a b/p.iso"]), true), Mode::PlayDirect { game: Some("/a b/p.iso".into()) });
        assert_eq!(mode(&args(&["--game", "/x"]), true), Mode::Window { game: Some("/x".into()) });
        assert_eq!(mode(&args(&[]), true), Mode::Window { game: None });
        // the program's own name is never an argument
        assert_eq!(mode(&["--prepare".to_string()], false), Mode::Window { game: None });
    }

    /// recomplauncher.json starts the program it names with the arguments this
    /// command line reads, and hands prepare the inputs it declares.
    #[test]
    fn profile_command_lines() {
        let p = profile();
        let start: Vec<String> = serde_json::from_value(p["start"]["args"].clone()).unwrap();
        let prep: Vec<String> = serde_json::from_value(p["prepare"]["args"].clone()).unwrap();
        assert_eq!(p["start"]["program"], p["prepare"]["program"]);
        assert_eq!(p["start"]["program"][0], "PES 2013 Launcher.app/Contents/MacOS/pes2013-launcher");
        let argv = |v: &[String]| std::iter::once("launcher".to_string()).chain(v.iter().map(|a| a.replace("{game}", "/g/pes.iso").replace("{input:update}", "/g/u.pkg").replace("{input:pack}", "/g/dp6"))).collect::<Vec<_>>();
        assert_eq!(mode(&argv(&start), true), Mode::PlayDirect { game: Some("/g/pes.iso".into()) });
        assert_eq!(
            mode(&argv(&prep), true),
            Mode::Prepare(PrepareArgs { game: Some("/g/pes.iso".into()), update: Some("/g/u.pkg".into()), pack: Some("/g/dp6".into()), unfilled: vec![] })
        );
        // every {input:<id>} names an input of the profile, and the update is required
        let ids: Vec<&str> = p["inputs"].as_array().unwrap().iter().map(|i| i["id"].as_str().unwrap()).collect();
        for a in &prep {
            if let Some(id) = a.split("{input:").nth(1).and_then(|r| r.split('}').next()) {
                assert!(ids.contains(&id), "{a}");
            }
        }
        let update = p["inputs"].as_array().unwrap().iter().find(|i| i["role"] == "update").unwrap();
        assert_eq!(update["optional"].as_bool().unwrap_or(false), false);
        assert!(p["inputs"].as_array().unwrap().iter().all(|i| i["role"] != "key"), "the key file is never an input");
    }

    #[test]
    fn exit_codes_are_distinct_and_in_the_profile() {
        let codes: std::collections::BTreeSet<i32> = Exit::ALL.iter().map(|e| e.code()).collect();
        assert_eq!(codes.len(), Exit::ALL.len());
        assert_eq!(Exit::Ok.code(), 0);
        // recomplauncher.json says each one to the player, word for word
        let p = profile();
        let said = p["exit_codes"].as_object().unwrap();
        assert_eq!(said.len(), Exit::ALL.len());
        for e in Exit::ALL {
            assert_eq!(said[&e.code().to_string()].as_str(), Some(e.says()), "{e:?}");
        }
        assert_eq!(classify(Some("build"), &["build: REFUSED: held by builder (pid 4)".into()]), Exit::Running);
        assert_eq!(classify(Some("build"), &["build: REFUSED: only 3 GB free".into()]), Exit::Build);
        assert_eq!(classify(Some("venv"), &["ERROR: could not install the Python packages (they come from the internet)".into()]), Exit::Sources);
        assert_eq!(classify(Some("toolkit"), &["fatal: unable to access 'https://github.com/erikomis/ps3recomp.git/': Could not resolve host: github.com".into()]), Exit::Sources);
        assert_eq!(classify(Some("game"), &["ERROR: that .pkg is not the BLUS31029 01.04 update".into()]), Exit::Copy);
        assert_eq!(classify(Some("game"), &["cp: x: No space left on device".into()]), Exit::Build);
        assert_eq!(classify(Some("decrypt"), &["decrypt_self: no key for revision 0x19".into()]), Exit::NeedsPlayer);
        assert_eq!(classify(Some("build"), &["ninja: build stopped: subcommand failed.".into()]), Exit::Build);
        assert_eq!(classify(None, &[]), Exit::Build);
    }

    /// RecompLauncher edits launcher.json with the profile's settings: every key
    /// is one of Settings' own, every value it writes reads back as that value,
    /// and the defaults are the launcher's.
    #[test]
    fn profile_settings_are_the_launchers() {
        let p = profile();
        assert_eq!(p["config"][0]["file"][0]["path"], "{home}/Library/Application Support/pes13-recomp/launcher.json");
        let ours = serde_json::to_value(Settings::default()).unwrap();
        // numbers as numbers (an f32 setting comes back as 0.3499999940...)
        let same = |a: &serde_json::Value, b: &serde_json::Value| match (a.as_f64(), b.as_f64()) {
            (Some(x), Some(y)) => (x - y).abs() < 1e-6,
            _ => a == b,
        };
        let groups: Vec<&str> = p["groups"].as_array().unwrap().iter().map(|g| g["id"].as_str().unwrap()).collect();
        for s in p["settings"].as_array().unwrap() {
            let id = s["id"].as_str().unwrap();
            assert!(groups.contains(&s["group"].as_str().unwrap()), "{id}");
            for (k, v) in s["defaults"].as_object().unwrap() {
                let want: serde_json::Value = serde_json::from_str(v.as_str().unwrap()).unwrap();
                assert!(same(&ours[k], &want), "{id}: default of {k} is {} here, {want} in the profile", ours[k]);
            }
            let mut writes: Vec<(String, serde_json::Value)> = Vec::new();
            for c in s["choices"].as_array().into_iter().flatten() {
                for (k, v) in c["set"].as_object().unwrap() {
                    writes.push((k.clone(), serde_json::from_str(v.as_str().unwrap()).unwrap()));
                }
            }
            if let Some(sl) = s.get("slider") {
                let key = sl["key"].as_str().unwrap().to_string();
                // what "%.2f" / "%d" write, at both ends and a step in
                let fmt = sl["format"].as_str().unwrap();
                let (min, max, step) = (sl["min"].as_f64().unwrap(), sl["max"].as_f64().unwrap(), sl["step"].as_f64().unwrap());
                for x in [min, min + step, max] {
                    let text = if fmt == "%d" { format!("{}", x.round() as i64) } else { format!("{x:.2}") };
                    writes.push((key.clone(), serde_json::from_str(&text).unwrap()));
                }
            }
            assert!(!writes.is_empty(), "{id}");
            for (k, v) in writes {
                assert!(ours.get(&k).is_some(), "{id}: {k} is not a launcher setting");
                let mut file = ours.clone();
                file[&k] = v.clone();
                let back = serde_json::to_value(serde_json::from_value::<Settings>(file).unwrap_or_else(|e| panic!("{id}: {k}={v}: {e}"))).unwrap();
                assert!(same(&back[&k], &v), "{id}: {k}={v} reads back as {}", back[&k]);
            }
        }
        // a file with only the profile's keys (RecompLauncher's first write)
        // is a whole settings file: everything else at its default
        let only: Settings = serde_json::from_str(r#"{"windowMode":"borderless","aniso":8}"#).unwrap();
        assert_eq!((only.window_mode.as_str(), only.aniso, only.audio_volume), ("borderless", 8, 100));
    }

    #[test]
    fn progress_lines() {
        assert_eq!(progress_line(0.25, "Translating  the\ngame's code"), "progress 0.250 Translating the game's code");
        assert_eq!(progress_line(1.7, "x"), "progress 1.000 x");
        assert_eq!(progress_line(-1.0, "x"), "progress 0.000 x");
        // RecompLauncher reads "progress <n> <text>": a script line must not pass for one
        assert_eq!(log_line("progress 0.5 fake"), "  progress 0.5 fake");
        assert_eq!(log_line("\x1b[1m==> lift\x1b[0m"), "==> lift");

        let mut r = Reporter::default();
        assert_eq!(r.update(0.1, "a").as_deref(), Some("progress 0.100 a"));
        assert_eq!(r.update(0.102, "a"), None, "under half a percent");
        assert_eq!(r.update(0.05, "b").as_deref(), Some("progress 0.102 b"), "never back");
        assert_eq!(r.update(0.2, "b").as_deref(), Some("progress 0.200 b"));
        assert_eq!(r.force(0.0, "failed"), "progress 0.200 failed");
        assert_eq!(r.update(1.0, "failed").as_deref(), Some("progress 1.000 failed"));
    }

    /// install.zsh's output on a fresh Mac, step by step (tools/rebuild.sh
    /// prints its own bold "==> <step>" and "==> done").
    const INSTALL: &[&str] = &[
        "$ install   # into /Users/x/Library/Application Support/pes13-recomp",
        "==> sources",
        "  {\"commit\":\"d304521\"}",
        "==> toolkit",
        "Cloning into '/Users/x/Library/Application Support/pes13-recomp/toolkit'...",
        "==> venv",
        "==> game",
        "  update: BLUS31029 01.04 Pro Evolution Soccer 2013",
        "\x1b[1m==> decrypt\x1b[0m",
        "\x1b[1m==> done\x1b[0m",
        "\x1b[1m==> analyse\x1b[0m",
        "\x1b[1m==> done\x1b[0m",
        "\x1b[1m==> lift\x1b[0m",
        "[12/24] lifting unit 12",
        "\x1b[1m==> done\x1b[0m",
        "==> spu",
        "  done by an earlier run",
        "\x1b[1m==> build\x1b[0m",
        "[812/1490] Building C object",
        "\x1b[1m==> done\x1b[0m",
        "==> done",
    ];

    #[test]
    fn install_steps_move_the_bar_forward() {
        assert_eq!(&STEP_IDS[..], &install::STEPS[..9], "the window's steps, without the Option File's");
        let mut steps = StepTracker::default();
        let mut rep = Reporter::default();
        let mut last = -1.0;
        let mut stages = Vec::new();
        for (i, l) in INSTALL.iter().enumerate() {
            let t = i as f64 * 600.0;
            steps.feed(l, t);
            for dt in [0.0, 60.0, 599.0] {
                let f = overall(steps.fraction(t + dt));
                assert!((0.0..=1.0).contains(&f));
                rep.update(f, stage_text(steps.stage()));
                assert!(rep.last() >= last, "{l}: {} < {last}", rep.last());
                last = rep.last();
            }
            if let Some(s) = steps.stage() {
                if stages.last() != Some(&s) {
                    stages.push(s);
                }
            }
        }
        assert_eq!(stages, STEP_IDS);
        steps.finish(true);
        assert!((steps.fraction(1e9) - 1.0).abs() < 1e-9);
        assert!((overall(1.0) - INSTALL_TO).abs() < 1e-9 && overall(0.0) == INSTALL_FROM);

        // a second run: steps it went past count as skipped
        let mut s2 = StepTracker::default();
        s2.feed("==> game", 0.0);
        assert_eq!(s2.stage(), Some("game"));
        assert!(s2.fraction(0.0) > 5.0 / 97.0);
        // a failure keeps the step it stopped at
        s2.finish(false);
        assert_eq!(s2.stage(), Some("game"));
        // lines that only look like steps change nothing
        let mut s3 = StepTracker::default();
        for l in ["==>lift", "==> LIFT", "  ==> lift", "==> lifting", "progress 0.5 lift"] {
            s3.feed(l, 0.0);
        }
        assert_eq!(s3.stage(), None);
    }

    fn sfb(id: &str) -> Vec<u8> {
        let mut d = vec![0u8; 0x600];
        d[..4].copy_from_slice(b".SFB");
        d[4..6].copy_from_slice(&[0, 1]);
        d[0x20..0x2B].copy_from_slice(b"HYBRID_FLAG");
        d[0x30..0x38].copy_from_slice(&[0, 0, 2, 0, 0, 0, 0, 0x20]);
        d[0x40..0x48].copy_from_slice(b"TITLE_ID");
        d[0x50..0x58].copy_from_slice(&[0, 0, 2, 0x20, 0, 0, 0, 0x10]);
        d[0x220..0x220 + id.len()].copy_from_slice(id.as_bytes());
        d
    }

    fn sfo(id: &str) -> Vec<u8> {
        saves::psf_write(&[
            saves::PsfEntry { key: "TITLE_ID".into(), fmt: saves::PSF_UTF8, data: format!("{id}\0").into_bytes(), max_len: 16 },
            saves::PsfEntry { key: "VERSION".into(), fmt: saves::PSF_UTF8, data: b"01.00\0".to_vec(), max_len: 8 },
        ])
    }

    /// A directory record: its extent, size, flags and name.
    fn rec(lba: u32, size: u32, dir: bool, name: &[u8]) -> Vec<u8> {
        let len = 33 + name.len() + (name.len() + 1) % 2;
        let mut r = vec![0u8; len];
        r[0] = len as u8;
        r[2..6].copy_from_slice(&lba.to_le_bytes());
        r[6..10].copy_from_slice(&lba.to_be_bytes());
        r[10..14].copy_from_slice(&size.to_le_bytes());
        r[14..18].copy_from_slice(&size.to_be_bytes());
        r[25] = if dir { 2 } else { 0 };
        r[32] = name.len() as u8;
        r[33..33 + name.len()].copy_from_slice(name);
        r
    }

    /// A small ISO 9660 image: the root (sector 18) with PS3_DISC.SFB (sector
    /// 19) and PS3_GAME/ (sector 20) holding PARAM.SFO (sector 21).
    pub(crate) fn fake_iso(sfb_id: &str, sfo_id: &str) -> Vec<u8> {
        let s = 2048usize;
        let mut img = vec![0u8; 22 * s + 2048];
        let (sfb, sfo) = (sfb(sfb_id), sfo(sfo_id));
        let pvd = &mut img[16 * s..17 * s];
        pvd[0] = 1;
        pvd[1..6].copy_from_slice(b"CD001");
        pvd[6] = 1;
        pvd[128..130].copy_from_slice(&2048u16.to_le_bytes());
        pvd[156..156 + 34].copy_from_slice(&rec(18, 2048, true, &[0]));
        let term = &mut img[17 * s..18 * s];
        term[0] = 255;
        term[1..6].copy_from_slice(b"CD001");
        let root: Vec<u8> = [rec(18, 2048, true, &[0]), rec(18, 2048, true, &[1]), rec(19, sfb.len() as u32, false, b"PS3_DISC.SFB;1"), rec(20, 2048, true, b"PS3_GAME")].concat();
        img[18 * s..18 * s + root.len()].copy_from_slice(&root);
        img[19 * s..19 * s + sfb.len()].copy_from_slice(&sfb);
        let game: Vec<u8> = [rec(20, 2048, true, &[0]), rec(18, 2048, true, &[1]), rec(21, sfo.len() as u32, false, b"PARAM.SFO;1")].concat();
        img[20 * s..20 * s + game.len()].copy_from_slice(&game);
        img[21 * s..21 * s + sfo.len()].copy_from_slice(&sfo);
        img
    }

    #[test]
    fn sfb_ids() {
        assert_eq!(sfb_title_id(&sfb("BLUS-31029")).as_deref(), Some("BLUS-31029"));
        assert_eq!(id_key("BLUS-31029"), TITLE_ID);
        assert_eq!(sfb_title_id(b"not an sfb at all, not at all, not at all, not at all, no"), None);
        // an empty slot before TITLE_ID is passed over
        let mut gap = sfb("BLUS-31029");
        gap[0x20..0x40].fill(0);
        assert_eq!(sfb_title_id(&gap).as_deref(), Some("BLUS-31029"));
        let mut cut = sfb("BLUS-31029");
        cut.truncate(0x100);
        assert_eq!(sfb_title_id(&cut), None, "the value lies past the end");
    }

    #[test]
    fn disc_images() {
        let d = tmp("iso");
        let good = d.join("Pro Evolution Soccer 2013 (USA).iso");
        fs::write(&good, fake_iso("BLUS-31029", "BLUS31029")).unwrap();
        assert_eq!(check_copy(&good).unwrap(), (GameCopy::Image(good.clone()), "01.00".to_string()));
        let other = d.join("backup-07.iso");
        fs::write(&other, fake_iso("BLES-01746", "BLES01746")).unwrap();
        assert!(check_copy(&other).unwrap_err().contains("BLES-01746"));
        let plain = d.join("notes.iso");
        fs::write(&plain, vec![0u8; 40000]).unwrap();
        assert!(check_copy(&plain).unwrap_err().contains("isn't a disc image"));
        let small = d.join("tiny.iso");
        fs::write(&small, b"x").unwrap();
        assert!(check_copy(&small).is_err());
        // an ISO 9660 image of something else: no PS3_DISC.SFB
        let mut cd = fake_iso("BLUS-31029", "BLUS31029");
        let at = cd.windows(12).position(|w| w == b"PS3_DISC.SFB").unwrap();
        cd[at..at + 12].copy_from_slice(b"README.TXT;1");
        let cd_path = d.join("cd.iso");
        fs::write(&cd_path, cd).unwrap();
        assert!(check_copy(&cd_path).unwrap_err().contains("no PS3_DISC.SFB"));
        assert!(check_copy(&d.join("missing.iso")).unwrap_err().contains("isn't there"));
        fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn disc_folders() {
        let d = tmp("folder");
        let disc = d.join("BLUS31029");
        assert!(check_copy(&disc).is_err());
        fs::create_dir_all(disc.join("PS3_GAME/USRDIR")).unwrap();
        assert!(check_copy(&disc).unwrap_err().contains("no PS3_GAME"));
        fs::write(disc.join("PS3_GAME/PARAM.SFO"), sfo("BLUS31029")).unwrap();
        assert!(check_copy(&disc).unwrap_err().contains("EBOOT.BIN"));
        fs::write(disc.join("PS3_GAME/USRDIR/EBOOT.BIN"), b"x").unwrap();
        fs::write(disc.join("PS3_DISC.SFB"), sfb("BLUS-31029")).unwrap();
        assert_eq!(check_copy(&disc).unwrap(), (GameCopy::Folder(disc.clone()), "01.00".to_string()));
        // PS3_GAME itself is taken for its disc
        assert_eq!(check_copy(&disc.join("PS3_GAME")).unwrap().0, GameCopy::Folder(disc.clone()));
        // another region, in either file
        fs::write(disc.join("PS3_DISC.SFB"), sfb("BLES-01746")).unwrap();
        assert!(check_copy(&disc).unwrap_err().contains("BLES-01746"));
        fs::remove_file(disc.join("PS3_DISC.SFB")).unwrap();
        assert!(check_copy(&disc).is_ok(), "PS3_DISC.SFB is not required in a folder");
        fs::write(disc.join("PS3_GAME/PARAM.SFO"), sfo("BLES01746")).unwrap();
        assert!(check_copy(&disc).unwrap_err().contains("BLES01746"));
        fs::remove_dir_all(&d).unwrap();
    }

    fn pkg(path: &Path, id: &str) {
        let mut h = vec![0u8; 0x100];
        h[..4].copy_from_slice(b"\x7fPKG");
        h[0x30..0x30 + id.len()].copy_from_slice(id.as_bytes());
        fs::write(path, h).unwrap();
    }

    /// The update, the key file and the data pack for a prepare: from the
    /// command line, else as the window remembered them; the key file never
    /// from the command line, and only looked at.
    #[test]
    fn install_files() {
        let d = tmp("inputs");
        let data = d.join("data");
        fs::create_dir_all(&data).unwrap();
        let iso = d.join("pes.iso");
        fs::write(&iso, fake_iso("BLUS-31029", "BLUS31029")).unwrap();
        let image = GameCopy::Image(iso.clone());
        let folder = GameCopy::Folder(d.join("disc"));
        let up = d.join("update.pkg");
        pkg(&up, "UP0101-BLUS31029_00-PES2013USPATCH04");
        let keys = d.join("my keys.txt");
        fs::write(&keys, "not read").unwrap();
        let given = PrepareArgs { game: Some(iso.clone()), update: Some(up.clone()), ..Default::default() };
        let none = install::Inputs::default();
        let window = install::Inputs { keys: keys.to_string_lossy().into(), ..Default::default() };

        // no key file anywhere: the player has to add it (in the window)
        let (e, why) = install_inputs(&image, &given, &none, &data, false, false).unwrap_err();
        assert_eq!(e, Exit::NeedsPlayer);
        assert!(why.contains("Install the game") && why.contains("keys/self_keys.txt"), "{why}");
        // ... unless the EBOOT is decrypted already
        assert!(install_inputs(&image, &given, &none, &data, true, false).unwrap().keys.is_empty());
        // the window's, then the data folder's keys/self_keys.txt
        let i = install_inputs(&image, &given, &window, &data, false, false).unwrap();
        assert_eq!((i.iso.as_str(), i.pkg.as_str(), i.keys.as_str()), (iso.to_str().unwrap(), up.to_str().unwrap(), keys.to_str().unwrap()));
        assert!(i.option_file.is_empty() && i.save_keys.is_empty() && i.pack.is_empty());
        fs::create_dir_all(data.join("keys")).unwrap();
        fs::write(keys_fallback(&data), "not read either").unwrap();
        assert_eq!(install_inputs(&image, &given, &none, &data, false, false).unwrap().keys, keys_fallback(&data).to_string_lossy());

        // the update: given, else the window's, else needed until EBOOT.BIN is there
        let no_update = PrepareArgs { game: Some(iso.clone()), ..Default::default() };
        let (e, why) = install_inputs(&image, &no_update, &window, &data, false, false).unwrap_err();
        assert_eq!(e, Exit::Copy);
        assert!(why.contains("01.04"), "{why}");
        let remembered = install::Inputs { pkg: up.to_string_lossy().into(), ..window.clone() };
        assert_eq!(install_inputs(&image, &no_update, &remembered, &data, false, false).unwrap().pkg, up.to_string_lossy());
        assert!(install_inputs(&image, &no_update, &window, &data, false, true).unwrap().pkg.is_empty());
        let other = d.join("other.pkg");
        pkg(&other, "UP9000-BCUS98120_00-RESISTANCE");
        let wrong = PrepareArgs { update: Some(other.clone()), ..Default::default() };
        let (e, why) = install_inputs(&image, &wrong, &window, &data, false, false).unwrap_err();
        assert_eq!(e, Exit::Copy);
        assert!(why.contains("not the BLUS31029"), "{why}");

        // a folder links no image; the data pack from the command line, else the window's (when still there)
        let pack = d.join("dp6");
        fs::create_dir_all(pack.join("USRDIR")).unwrap();
        let with_pack = PrepareArgs { update: Some(up.clone()), pack: Some(pack.clone()), ..Default::default() };
        let i = install_inputs(&folder, &with_pack, &window, &data, false, false).unwrap();
        assert_eq!((i.iso.as_str(), i.pack.as_str()), ("", pack.to_str().unwrap()));
        let gone = install::Inputs { pack: d.join("gone").to_string_lossy().into(), ..window.clone() };
        assert!(install_inputs(&folder, &given, &gone, &data, false, false).unwrap().pack.is_empty());
        let bad_pack = PrepareArgs { update: Some(up.clone()), pack: Some(d.join("disc")), ..Default::default() };
        fs::create_dir_all(d.join("disc")).unwrap();
        assert_eq!(install_inputs(&folder, &bad_pack, &window, &data, false, false).unwrap_err().0, Exit::Copy);

        // the key files were never written
        assert_eq!(fs::read_to_string(&keys).unwrap(), "not read");
        assert_eq!(fs::read_to_string(keys_fallback(&data)).unwrap(), "not read either");
        fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn running_is_this_games_build() {
        assert_eq!(running_pattern(), "BLUS31029/PES2013Recomp( |$)");
    }
}
