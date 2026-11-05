//! "Install the game": the player's own files in, a build Play can run out.
//! The work is `install.zsh` (bundled into the binary), run by lib.rs's
//! `start_install` in the data folder; this module checks the inputs before it
//! starts and knows the folders it makes. Everything an install writes is inside
//! the data folder: `port/` (PES_ROOT), `toolkit/` (PS3RECOMP_DIR), `venv/`
//! (PES_VENV) and, with an Option File, `profiles/Option File/`.
//!
//! The key files are only checked to exist here. Their paths are handed to the
//! tools that need them (tools/decrypt_self.py, tools/install_savedata.py); the
//! launcher never opens them.

use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

pub const SCRIPT: &str = include_str!("install.zsh");

/// The steps `install.zsh` announces, in order (src/progress.ts has the same).
#[cfg(test)]
pub const STEPS: &[&str] = &["sources", "toolkit", "venv", "game", "decrypt", "analyse", "lift", "spu", "build", "optionfile"];

/// The free space an install asks for: the lift is about 1.7 GB of C++, the
/// build about 2 GB with the 400 MB executable, the toolkit and the venv 0.1 GB,
/// with room for the compile on the way.
pub const NEED_GB: u64 = 10;

/// Homebrew formulas the build needs (git and the compiler come with Apple's
/// Command Line Tools), and what shows each one is installed.
pub const BREW_NEEDS: &[(&str, &[&str])] = &[
    ("cmake", &["bin/cmake"]),
    ("ninja", &["bin/ninja"]),
    ("sdl2", &["lib/libSDL2.dylib", "opt/sdl2"]),
    ("python@3.12", &["bin/python3.12", "opt/python@3.12"]),
];

pub fn brew_missing(prefix: &Path) -> Vec<&'static str> {
    BREW_NEEDS.iter().filter(|(_, marks)| !marks.iter().any(|m| prefix.join(m).exists())).map(|(f, _)| *f).collect()
}

pub struct Layout {
    pub data: PathBuf,
}

impl Layout {
    pub fn port(&self) -> PathBuf {
        self.data.join("port")
    }
    pub fn toolkit(&self) -> PathBuf {
        self.data.join("toolkit")
    }
    pub fn venv(&self) -> PathBuf {
        self.data.join("venv")
    }
    pub fn log(&self) -> PathBuf {
        self.data.join("install.log")
    }
}

/// What the player chose, as the Home card sends it (and the settings keep it).
#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(rename_all = "camelCase", default)]
pub struct Inputs {
    /// The US disc image (BLUS31029).
    pub iso: String,
    /// The 01.04 update package.
    pub pkg: String,
    /// The key file for the EBOOT (self_keys.txt format).
    pub keys: String,
    /// Optional: the Data Pack 6 folder or .pkg.
    pub pack: String,
    /// Optional: a folder of PS3 saves (the Option File), and its key file.
    pub option_file: String,
    pub save_keys: String,
}

/// A package's content id (offset 0x30 of its header), e.g.
/// "UP0101-BLUS31029_00-PES2013USPATCH04".
pub fn pkg_content_id(path: &Path) -> Option<String> {
    let mut f = fs::File::open(path).ok()?;
    let mut head = [0u8; 0x60];
    f.read_exact(&mut head).ok()?;
    if &head[..4] != b"\x7fPKG" {
        return None;
    }
    let id = &head[0x30..0x54];
    let end = id.iter().position(|&b| b == 0).unwrap_or(id.len());
    std::str::from_utf8(&id[..end]).ok().map(str::to_string)
}

fn file(what: &str, p: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(p.trim());
    if p.trim().is_empty() {
        return Err(format!("choose {what} first"));
    }
    if !path.is_absolute() || path.components().any(|c| matches!(c, std::path::Component::ParentDir)) {
        return Err(format!("{what}: {} is not a plain absolute path", path.display()));
    }
    if !path.is_file() {
        return Err(format!("{what}: {} is not there", path.display()));
    }
    Ok(path)
}

/// The inputs, checked as far as can be without opening the key files: the
/// image is an .iso, the package is this game's update, the data pack is a
/// folder with USRDIR or this game's package, the Option File holds this game's
/// saves from a console.
pub fn check(i: &Inputs, have_elf: bool, have_bin: bool) -> Result<Checked, String> {
    let iso = file("the disc image (.iso)", &i.iso)?;
    if !iso.extension().is_some_and(|e| e.eq_ignore_ascii_case("iso")) {
        return Err(format!("{}: not an .iso", iso.display()));
    }
    // the update is needed only until game/EBOOT.BIN is there
    let pkg = if i.pkg.trim().is_empty() && have_bin {
        None
    } else {
        let p = file("the 01.04 update (.pkg)", &i.pkg)?;
        match pkg_content_id(&p) {
            Some(id) if id.contains("BLUS31029") => {}
            Some(id) => return Err(format!("{}: that package is {id}, not the BLUS31029 update", p.display())),
            None => return Err(format!("{}: not a PS3 package", p.display())),
        }
        Some(p)
    };
    // the key file decrypts the EBOOT once; after that it is not needed
    let keys = if i.keys.trim().is_empty() && have_elf { None } else { Some(file("the key file", &i.keys)?) };
    let pack = if i.pack.trim().is_empty() {
        None
    } else {
        let p = PathBuf::from(i.pack.trim());
        if p.is_dir() {
            if !p.join("USRDIR").is_dir() {
                return Err(format!("{}: a data pack folder has a USRDIR inside", p.display()));
            }
        } else {
            let p = file("the data pack", &i.pack)?;
            if !pkg_content_id(&p).is_some_and(|id| id.contains("BLUS31029")) {
                return Err(format!("{}: not a BLUS31029 package", p.display()));
            }
        }
        Some(p)
    };
    let (option_file, save_keys) = if i.option_file.trim().is_empty() {
        (None, None)
    } else {
        let src = crate::profiles::saves_source(Path::new(i.option_file.trim()))?;
        (Some(src), Some(file("the Option File's key file (savedata_keys.txt)", &i.save_keys)?))
    };
    Ok(Checked { iso, pkg, keys, pack, option_file, save_keys })
}

#[derive(Debug)]
pub struct Checked {
    pub iso: PathBuf,
    pub pkg: Option<PathBuf>,
    pub keys: Option<PathBuf>,
    pub pack: Option<PathBuf>,
    pub option_file: Option<PathBuf>,
    pub save_keys: Option<PathBuf>,
}

impl Checked {
    /// The environment `install.zsh` reads.
    pub fn env(&self, l: &Layout, stage: &Path) -> Vec<(String, String)> {
        let s = |p: &Path| p.to_string_lossy().into_owned();
        let o = |p: &Option<PathBuf>| p.as_deref().map(s).unwrap_or_default();
        vec![
            ("PES_DATA".into(), s(&l.data)),
            ("PES_STAGE".into(), s(stage)),
            ("PES_ISO".into(), s(&self.iso)),
            ("PES_PKG".into(), o(&self.pkg)),
            ("PES_KEYS".into(), o(&self.keys)),
            ("PES_PACK".into(), o(&self.pack)),
            ("PES_OPTIONFILE".into(), o(&self.option_file)),
            ("PES_SAVEKEYS".into(), o(&self.save_keys)),
        ]
    }
}

/// The bundled sources: a folder with tools/rebuild.sh and BUILD_INFO.json.
pub fn is_stage(p: &Path) -> bool {
    p.join("tools/rebuild.sh").is_file() && p.join("tools/install_savedata.py").is_file() && p.join("BUILD_INFO.json").is_file()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("pes-install-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    fn pkg(path: &Path, id: &str) {
        let mut h = vec![0u8; 0x100];
        h[..4].copy_from_slice(b"\x7fPKG");
        h[0x30..0x30 + id.len()].copy_from_slice(id.as_bytes());
        fs::write(path, h).unwrap();
    }

    #[test]
    fn inputs_are_checked() {
        let d = tmp("inputs");
        let iso = d.join("PES 2013.iso");
        fs::write(&iso, "iso").unwrap();
        let up = d.join("update.pkg");
        pkg(&up, "UP0101-BLUS31029_00-PES2013USPATCH04");
        let keys = d.join("self_keys.txt");
        fs::write(&keys, "not read").unwrap();
        let ok = Inputs { iso: iso.to_string_lossy().into(), pkg: up.to_string_lossy().into(), keys: keys.to_string_lossy().into(), ..Default::default() };
        let c = check(&ok, false, false).unwrap();
        assert_eq!(c.pkg.as_deref(), Some(up.as_path()));
        assert!(c.pack.is_none() && c.option_file.is_none());

        // each input refused on its own
        let mut i = ok.clone();
        i.iso = d.join("x.img").to_string_lossy().into();
        fs::write(d.join("x.img"), "").unwrap();
        assert!(check(&i, false, false).unwrap_err().contains("not an .iso"));
        let other = d.join("other.pkg");
        pkg(&other, "UP9000-BCUS98120_00-RESISTANCE");
        let mut i = ok.clone();
        i.pkg = other.to_string_lossy().into();
        assert!(check(&i, false, false).unwrap_err().contains("not the BLUS31029"));
        fs::write(&other, "not a pkg").unwrap();
        assert!(check(&i, false, false).unwrap_err().contains("not a PS3 package"));
        let mut i = ok.clone();
        i.keys = String::new();
        assert!(check(&i, false, false).is_err());
        assert!(check(&i, true, false).is_ok(), "no key file needed once EBOOT.elf is there");
        let mut i = ok.clone();
        i.pkg = String::new();
        assert!(check(&i, false, false).is_err());
        assert!(check(&i, false, true).is_ok(), "no package needed once EBOOT.BIN is there");
        let mut i = ok.clone();
        i.iso = format!("{}/../{}", d.display(), "PES 2013.iso");
        assert!(check(&i, false, false).unwrap_err().contains("plain absolute"));

        // the data pack: a folder with USRDIR, or the game's package
        let mut i = ok.clone();
        i.pack = d.join("pack").to_string_lossy().into();
        fs::create_dir_all(d.join("pack")).unwrap();
        assert!(check(&i, false, false).is_err());
        fs::create_dir_all(d.join("pack/USRDIR")).unwrap();
        assert!(check(&i, false, false).unwrap().pack.is_some());
        let dp = d.join("dp6.pkg");
        pkg(&dp, "UP0101-BLUS31029_00-PES2013DATAPACK6");
        i.pack = dp.to_string_lossy().into();
        assert!(check(&i, false, false).is_ok());

        // the Option File needs its key file and a console's saves
        let of = d.join("usb/PS3/SAVEDATA/BLUS31029EEDIT");
        fs::create_dir_all(&of).unwrap();
        fs::write(of.join("PARAM.SFO"), "sfo").unwrap();
        fs::write(of.join("PARAM.PFD"), vec![0xFFu8; 0x400]).unwrap();
        let mut i = ok.clone();
        i.option_file = d.join("usb").to_string_lossy().into();
        assert!(check(&i, false, false).unwrap_err().contains("savedata_keys"));
        i.save_keys = keys.to_string_lossy().into();
        let c = check(&i, false, false).unwrap();
        assert_eq!(c.option_file.as_deref(), Some(d.join("usb/PS3/SAVEDATA").as_path()));
        // nothing was opened for writing, and the key file is as it was
        assert_eq!(fs::read_to_string(&keys).unwrap(), "not read");
        fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn environment_for_the_script() {
        let d = tmp("env");
        let l = Layout { data: d.join("data") };
        let c = Checked { iso: d.join("a.iso"), pkg: None, keys: Some(d.join("k.txt")), pack: None, option_file: None, save_keys: None };
        let e: std::collections::BTreeMap<String, String> = c.env(&l, &d.join("stage")).into_iter().collect();
        assert_eq!(e["PES_DATA"], d.join("data").to_string_lossy());
        assert_eq!(e["PES_PKG"], "");
        assert_eq!(e["PES_KEYS"], d.join("k.txt").to_string_lossy());
        assert_eq!(l.port(), d.join("data/port"));
        fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn script_steps_match() {
        for s in STEPS {
            assert!(SCRIPT.contains(&format!("want {s}")) || SCRIPT.contains(&format!(" {s} ")), "{s}");
        }
        assert!(SCRIPT.contains("say done"));
        // the keys are handed over, never copied or printed
        assert!(!SCRIPT.contains("cat \"$PES_KEYS\"") && !SCRIPT.contains("cp \"$PES_KEYS\""));
    }

    #[test]
    fn brew_formulas() {
        let d = tmp("brew");
        assert_eq!(brew_missing(&d), vec!["cmake", "ninja", "sdl2", "python@3.12"]);
        fs::create_dir_all(d.join("bin")).unwrap();
        fs::write(d.join("bin/cmake"), "").unwrap();
        fs::create_dir_all(d.join("opt/sdl2")).unwrap();
        assert_eq!(brew_missing(&d), vec!["ninja", "python@3.12"]);
        fs::remove_dir_all(&d).unwrap();
    }
}
