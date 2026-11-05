//! Option File profiles: each one is a `PS3_GAMEDATA_ROOT`, that is a folder
//! holding `dev_hdd0/home/00000001/savedata` (the runtime appends that path)
//! and the runtime's `trophies/`. Three kinds:
//!
//! - **padrão**, built in: `<port>/rpcs3`, the tree `tools/run.sh` defaults to,
//!   with the owner's real Option File. Never deleted, and never installed
//!   into: `tools/install_savedata.py` replaces saves in its destination.
//! - **local**: `<data>/profiles/<name>/`, created here. Built in a hidden
//!   `.<name>.partial` beside it and renamed when complete, so a failure leaves
//!   nothing that looks like a profile.
//! - **external**: a folder registered in `<data>/profiles.json`. The launcher
//!   only reads it; removing the registration leaves its contents alone. The
//!   game itself writes there while it plays with that profile.
//!
//! Everything takes its folders from `Store`, so the tests run on temporary
//! directories. Nothing here opens `<data>/keys`: `keys_ready` only asks
//! whether the key file exists.

use crate::saves;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Component, Path, PathBuf};

/// The built-in profile's id and name.
pub const BUILTIN_ID: &str = "padrao";
pub const BUILTIN_NAME: &str = "padrão";
const REGISTRY: &str = "profiles.json";
const MAX_NAME: usize = 64;

pub struct Store {
    /// The launcher's data folder.
    pub data: PathBuf,
    /// `<port>/rpcs3`, when there is a port folder.
    pub builtin_root: Option<PathBuf>,
}

#[derive(Serialize, Deserialize, Clone, Copy, PartialEq, Eq, Debug)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Builtin,
    Local,
    External,
}

#[derive(Serialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub kind: Kind,
    /// What Play passes as PS3_GAMEDATA_ROOT.
    pub root: String,
    /// The savedata folder inside it.
    pub savedata: String,
    /// The launcher does not write here (a registered folder).
    pub read_only: bool,
    pub exists: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
struct External {
    name: String,
    path: String,
}

/// `<root>/dev_hdd0/home/00000001/savedata`.
pub fn savedata_of(root: &Path) -> PathBuf {
    root.join("dev_hdd0/home").join(saves::PORT_USER).join("savedata")
}

/// A name usable as a folder and shown as typed: letters of any alphabet,
/// digits, spaces, '-' and '_'. Anything else becomes '-', so "../x" cannot
/// leave the profiles folder. Reserved or empty names are refused.
pub fn sanitize_name(raw: &str) -> Result<String, String> {
    let mapped: String = raw
        .trim()
        .chars()
        .map(|c| if c.is_alphanumeric() || c == ' ' || c == '-' || c == '_' { c } else { '-' })
        .collect();
    let name = mapped.trim_matches(|c: char| c == '-' || c == ' ').to_string();
    if name.is_empty() {
        return Err("the profile needs a name".into());
    }
    if name.chars().count() > MAX_NAME {
        return Err(format!("the profile's name is longer than {MAX_NAME} characters"));
    }
    if name.eq_ignore_ascii_case(BUILTIN_ID) || name.to_lowercase() == BUILTIN_NAME {
        return Err(format!("{name}: that name is the built-in profile's"));
    }
    Ok(name)
}

impl Store {
    fn dir(&self) -> PathBuf {
        self.data.join("profiles")
    }
    fn registry(&self) -> PathBuf {
        self.data.join(REGISTRY)
    }
    fn local_root(&self, name: &str) -> PathBuf {
        self.dir().join(name)
    }
    /// The folder a new local profile is built in.
    pub fn stage_of(&self, name: &str) -> PathBuf {
        self.dir().join(format!(".{name}.partial"))
    }

    fn externals(&self) -> Vec<External> {
        fs::read_to_string(self.registry()).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default()
    }

    fn write_externals(&self, list: &[External]) -> Result<(), String> {
        fs::create_dir_all(&self.data).map_err(|e| format!("{}: {e}", self.data.display()))?;
        let p = self.registry();
        let tmp = p.with_extension("json.tmp");
        let text = serde_json::to_string_pretty(list).map_err(|e| e.to_string())?;
        fs::write(&tmp, text).map_err(|e| format!("{}: {e}", tmp.display()))?;
        fs::rename(&tmp, &p).map_err(|e| format!("{}: {e}", p.display()))
    }

    fn local_names(&self) -> Vec<String> {
        let mut names: Vec<String> = fs::read_dir(self.dir())
            .into_iter()
            .flatten()
            .flatten()
            .filter(|e| e.file_type().is_ok_and(|t| t.is_dir()))
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .filter(|n| !n.starts_with('.'))
            .collect();
        names.sort();
        names
    }

    /// A name no profile has (the file system ignores case, so this does too).
    fn free_name(&self, name: &str) -> Result<(), String> {
        let low = name.to_lowercase();
        let taken = self.local_names().iter().any(|n| n.to_lowercase() == low)
            || self.externals().iter().any(|e| e.name.to_lowercase() == low);
        if taken {
            Err(format!("{name}: there is a profile with that name"))
        } else {
            Ok(())
        }
    }
}

fn profile(id: String, name: String, kind: Kind, root: PathBuf) -> Profile {
    let savedata = savedata_of(&root);
    Profile {
        id,
        name,
        kind,
        read_only: kind == Kind::External,
        exists: root.is_dir(),
        root: root.to_string_lossy().into_owned(),
        savedata: savedata.to_string_lossy().into_owned(),
    }
}

/// Every profile: padrão, the local ones, the registered ones.
pub fn list(store: &Store) -> Vec<Profile> {
    let mut v = Vec::new();
    if let Some(r) = &store.builtin_root {
        v.push(profile(BUILTIN_ID.into(), BUILTIN_NAME.into(), Kind::Builtin, r.clone()));
    }
    for n in store.local_names() {
        v.push(profile(format!("local:{n}"), n.clone(), Kind::Local, store.local_root(&n)));
    }
    for e in store.externals() {
        v.push(profile(format!("ext:{}", e.name), e.name.clone(), Kind::External, PathBuf::from(&e.path)));
    }
    v
}

/// The profile with this id ("" is padrão, as in a settings file from before
/// profiles existed).
pub fn resolve(store: &Store, id: &str) -> Result<Profile, String> {
    let want = if id.is_empty() { BUILTIN_ID } else { id };
    list(store).into_iter().find(|p| p.id == want).ok_or_else(|| format!("{want}: no such profile"))
}

/// One folder a backup of this profile goes in (no separators in the id's name).
pub fn backup_key(id: &str) -> String {
    id.replace(':', "-")
}

/// The saves in a savedata folder: how many, their size, and whether the Edit
/// data is there. Only stats the files.
#[derive(Serialize, Default, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Usage {
    pub saves: u32,
    pub bytes: u64,
    pub has_edit: bool,
}

pub fn usage(savedata: &Path) -> Usage {
    let mut u = Usage::default();
    for e in fs::read_dir(savedata).into_iter().flatten().flatten() {
        let name = e.file_name().to_string_lossy().into_owned();
        if !saves::valid_slot(&name) || !e.file_type().is_ok_and(|t| t.is_dir()) {
            continue;
        }
        u.saves += 1;
        for f in fs::read_dir(e.path()).into_iter().flatten().flatten() {
            if let Ok(m) = f.metadata() {
                if m.is_file() {
                    u.bytes += m.len();
                }
            }
        }
        u.has_edit |= name == saves::EDIT_SLOT;
    }
    u
}

/// A new, empty local profile.
pub fn create_empty(store: &Store, raw_name: &str) -> Result<Profile, String> {
    let name = sanitize_name(raw_name)?;
    store.free_name(&name)?;
    let stage = store.stage_of(&name);
    let _ = fs::remove_dir_all(&stage);
    let saved = savedata_of(&stage);
    fs::create_dir_all(&saved).map_err(|e| format!("{}: {e}", saved.display()))?;
    commit(store, &name)
}

/// A new local profile with a copy of `from`'s saves and trophies. Only those:
/// padrão's root also holds the VFS tree with symlinks to the disc.
pub fn create_copy(store: &Store, raw_name: &str, from: &Profile) -> Result<Profile, String> {
    let name = sanitize_name(raw_name)?;
    store.free_name(&name)?;
    let stage = store.stage_of(&name);
    let _ = fs::remove_dir_all(&stage);
    let result = (|| -> Result<(), String> {
        fs::create_dir_all(savedata_of(&stage)).map_err(|e| format!("{}: {e}", stage.display()))?;
        let src = Path::new(&from.savedata);
        if src.is_dir() {
            saves::copy_tree(src, &savedata_of(&stage), &[])?;
        }
        let trophies = Path::new(&from.root).join("trophies");
        if trophies.is_dir() {
            saves::copy_tree(&trophies, &stage.join("trophies"), &[])?;
        }
        Ok(())
    })();
    if let Err(e) = result {
        let _ = fs::remove_dir_all(&stage);
        return Err(e);
    }
    commit(store, &name)
}

/// A new local profile from a .zip of saves (`saves::import_zip`, into the
/// stage). It backs up nothing: there is nothing there yet.
pub fn create_from_zip(store: &Store, raw_name: &str, zip: &Path, now: u64) -> Result<Profile, String> {
    let name = sanitize_name(raw_name)?;
    store.free_name(&name)?;
    let stage = store.stage_of(&name);
    let _ = fs::remove_dir_all(&stage);
    let loc = saves::Locations {
        port_savedata: savedata_of(&stage),
        rpcs3_hdd0: stage.join("no-rpcs3"),
        backups: stage.join(".import-work"),
    };
    let result = fs::create_dir_all(&loc.port_savedata).map_err(|e| e.to_string()).and_then(|()| saves::import_zip(&loc, zip, now));
    let _ = fs::remove_dir_all(&loc.backups);
    if let Err(e) = result {
        let _ = fs::remove_dir_all(&stage);
        return Err(e);
    }
    commit(store, &name)
}

/// Empty the stage for `tools/install_savedata.py` and return its destination.
pub fn prepare_install(store: &Store, raw_name: &str) -> Result<(String, PathBuf), String> {
    let name = sanitize_name(raw_name)?;
    store.free_name(&name)?;
    let stage = store.stage_of(&name);
    let _ = fs::remove_dir_all(&stage);
    let dst = savedata_of(&stage);
    fs::create_dir_all(&dst).map_err(|e| format!("{}: {e}", dst.display()))?;
    Ok((name, dst))
}

/// Turn a finished stage into the profile.
pub fn commit(store: &Store, name: &str) -> Result<Profile, String> {
    let (stage, root) = (store.stage_of(name), store.local_root(name));
    fs::rename(&stage, &root).map_err(|e| {
        let _ = fs::remove_dir_all(&stage);
        format!("{}: {e}", root.display())
    })?;
    Ok(profile(format!("local:{name}"), name.to_string(), Kind::Local, root))
}

pub fn abandon(store: &Store, name: &str) {
    let _ = fs::remove_dir_all(store.stage_of(name));
}

/// A folder to hand to `tools/install_savedata.py`: the one holding the saves
/// themselves, also when given the PS3 layout around them (`PS3/SAVEDATA`, or
/// `SAVEDATA`). Each of this game's saves must have the console's binary
/// PARAM.PFD. A folder this launcher or the tool made has a text list instead,
/// and its files are already in the clear: the tool would fail on those, so
/// that folder is refused here with a way forward.
pub fn saves_source(picked: &Path) -> Result<PathBuf, String> {
    let dir = [picked.join("PS3/SAVEDATA"), picked.join("SAVEDATA"), picked.to_path_buf()]
        .into_iter()
        .find(|d| !game_saves(d).is_empty())
        .ok_or_else(|| format!("{}: no {} saves in this folder", picked.display(), saves::TITLE_ID))?;
    for s in game_saves(&dir) {
        let pfd = fs::read(s.join("PARAM.PFD")).map_err(|e| format!("{}: {e}", s.join("PARAM.PFD").display()))?;
        if !console_pfd(&pfd) {
            return Err(format!(
                "{}: its PARAM.PFD is not the console's, so these saves are already decrypted. Register the folder, or copy it, instead",
                s.display()
            ));
        }
    }
    Ok(dir)
}

fn game_saves(dir: &Path) -> Vec<PathBuf> {
    fs::read_dir(dir)
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.file_name().is_some_and(|n| saves::valid_slot(&n.to_string_lossy())) && p.join("PARAM.SFO").is_file())
        .collect()
}

/// The console's PARAM.PFD: at least its header and table capacity, not the
/// runtime's short list of names.
fn console_pfd(d: &[u8]) -> bool {
    d.len() >= 0x78 && std::str::from_utf8(d).is_err()
}

/// A path with no `..` left to resolve, or an error.
fn no_traversal(p: &Path) -> Result<(), String> {
    if !p.is_absolute() {
        return Err(format!("{}: not an absolute path", p.display()));
    }
    if p.components().any(|c| matches!(c, Component::ParentDir)) {
        return Err(format!("{}: a path with .. in it is not accepted", p.display()));
    }
    Ok(())
}

/// Register a folder as a profile, without copying. Given the savedata folder
/// itself, its root is what gets registered. The folder must already have the
/// savedata tree; nothing is created in it.
pub fn register_external(store: &Store, raw_name: &str, path: &Path) -> Result<Profile, String> {
    let name = sanitize_name(raw_name)?;
    store.free_name(&name)?;
    no_traversal(path)?;
    let path = path.canonicalize().map_err(|e| format!("{}: {e}", path.display()))?;
    let suffix = savedata_of(Path::new(""));
    let root = if path.ends_with(&suffix) {
        path.ancestors().nth(suffix.components().count()).map(Path::to_path_buf).unwrap_or_else(|| path.clone())
    } else {
        path
    };
    if !savedata_of(&root).is_dir() {
        return Err(format!("{}: it has no {}", root.display(), suffix.display()));
    }
    let data = store.data.canonicalize().unwrap_or_else(|_| store.data.clone());
    if root.starts_with(data.join("keys")) || root.starts_with(data.join("profiles")) || root == data {
        return Err(format!("{}: that is inside the launcher's own folder", root.display()));
    }
    if store.builtin_root.as_ref().is_some_and(|b| b.canonicalize().is_ok_and(|b| b == root)) {
        return Err(format!("{}: that is the {BUILTIN_NAME} profile", root.display()));
    }
    let mut list = store.externals();
    list.push(External { name: name.clone(), path: root.to_string_lossy().into_owned() });
    store.write_externals(&list)?;
    Ok(profile(format!("ext:{name}"), name, Kind::External, root))
}

/// Delete a local profile's folder, or forget a registered one (its contents
/// stay). `confirm` must repeat the profile's name. padrão is refused.
pub fn delete(store: &Store, id: &str, confirm: &str) -> Result<(), String> {
    let p = resolve(store, id)?;
    if p.name != confirm {
        return Err("the confirmation does not match the profile's name".into());
    }
    match p.kind {
        Kind::Builtin => Err(format!("the {BUILTIN_NAME} profile cannot be deleted")),
        Kind::External => {
            let list: Vec<External> = store.externals().into_iter().filter(|e| e.name != p.name).collect();
            store.write_externals(&list)
        }
        Kind::Local => {
            let root = Path::new(&p.root);
            // the folder itself, directly under profiles/, and no symlink out of it
            let meta = fs::symlink_metadata(root).map_err(|e| format!("{}: {e}", root.display()))?;
            if !meta.is_dir() {
                return Err(format!("{}: not a folder", root.display()));
            }
            let parent = store.dir().canonicalize().map_err(|e| e.to_string())?;
            let real = root.canonicalize().map_err(|e| e.to_string())?;
            if real.parent() != Some(parent.as_path()) {
                return Err(format!("{}: not in the profiles folder", root.display()));
            }
            fs::remove_dir_all(&real).map_err(|e| format!("{}: {e}", real.display()))
        }
    }
}

/// The key file `tools/install_savedata.py` takes exists. Only looked at.
pub fn keys_file(data: &Path) -> PathBuf {
    data.join("keys/savedata_keys.txt")
}

/// What `tools/pes2013_edit.py` says about an Edit data file.
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct EditCounts {
    pub players: u32,
    pub teams: u32,
    pub rosters: u32,
}

pub fn parse_edit_json(json: &str) -> Result<EditCounts, String> {
    let v: serde_json::Value = serde_json::from_str(json).map_err(|e| e.to_string())?;
    let n = |k: &str| v[k].as_array().map(|a| a.len() as u32).ok_or_else(|| format!("no {k} in the tool's output"));
    Ok(EditCounts { players: n("players")?, teams: n("teams")?, rosters: n("rosters")? })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn store(tag: &str) -> (PathBuf, Store) {
        let root = std::env::temp_dir().join(format!("pes-profiles-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let root = root.canonicalize().unwrap();
        let s = Store { data: root.join("data"), builtin_root: Some(root.join("port/rpcs3")) };
        fs::create_dir_all(&s.data).unwrap();
        (root, s)
    }

    fn put_save(savedata: &Path, slot: &str, bytes: usize, pfd: &[u8]) {
        let d = savedata.join(slot);
        fs::create_dir_all(&d).unwrap();
        fs::write(d.join("PARAM.SFO"), saves::psf_write(&[])).unwrap();
        fs::write(d.join("PARAM.PFD"), pfd).unwrap();
        fs::write(d.join("DATA.BIN"), vec![7u8; bytes]).unwrap();
    }

    #[test]
    fn names_are_sanitized() {
        assert_eq!(sanitize_name("  Brasil 2026 ").unwrap(), "Brasil 2026");
        assert_eq!(sanitize_name("../../etc").unwrap(), "etc");
        assert_eq!(sanitize_name("a/b\\c").unwrap(), "a-b-c");
        assert_eq!(sanitize_name("Série A_B").unwrap(), "Série A_B");
        assert_eq!(sanitize_name(".hidden").unwrap(), "hidden");
        assert!(!sanitize_name("x\0y").unwrap().contains('\0'));
        for bad in ["", "   ", "..", "/", "padrão", "PADRAO", "Padrão"] {
            assert!(sanitize_name(bad).is_err(), "{bad:?}");
        }
        assert!(sanitize_name(&"x".repeat(65)).is_err());
        assert!(sanitize_name(&"x".repeat(64)).is_ok());
    }

    #[test]
    fn built_in_is_listed_and_cannot_be_deleted() {
        let (root, s) = store("builtin");
        let l = list(&s);
        assert_eq!(l.len(), 1);
        assert_eq!(l[0].id, BUILTIN_ID);
        assert_eq!(l[0].kind, Kind::Builtin);
        assert!(l[0].savedata.ends_with("port/rpcs3/dev_hdd0/home/00000001/savedata"));
        assert_eq!(resolve(&s, "").unwrap().id, BUILTIN_ID);
        assert!(delete(&s, BUILTIN_ID, BUILTIN_NAME).is_err());
        assert!(resolve(&s, "local:nope").is_err());
        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn create_copy_and_delete() {
        let (root, s) = store("copy");
        let builtin = s.builtin_root.clone().unwrap();
        put_save(&savedata_of(&builtin), "BLUS31029EEDIT", 1000, b"DATA.BIN\n");
        put_save(&savedata_of(&builtin), "BLUS31029EFACE001", 10, b"");
        // what a real padrão also holds, and what must stay out of a copy
        fs::create_dir_all(builtin.join("dev_hdd0/disc/BLUS31029")).unwrap();
        std::os::unix::fs::symlink("/", builtin.join("dev_hdd0/disc/BLUS31029/PS3_GAME")).unwrap();
        fs::create_dir_all(builtin.join("trophies")).unwrap();
        fs::write(builtin.join("trophies/NPWR03760_00.json"), "{}").unwrap();

        let e = create_empty(&s, "Vazio").unwrap();
        assert_eq!(e.id, "local:Vazio");
        assert!(Path::new(&e.savedata).is_dir());
        assert_eq!(usage(Path::new(&e.savedata)), Usage::default());
        assert!(create_empty(&s, "vazio").is_err(), "the same name in another case");

        let from = resolve(&s, BUILTIN_ID).unwrap();
        let c = create_copy(&s, "Cópia/1", &from).unwrap();
        assert_eq!(c.name, "Cópia-1");
        let u = usage(Path::new(&c.savedata));
        assert_eq!((u.saves, u.has_edit), (2, true));
        assert_eq!(u.bytes, usage(&savedata_of(&builtin)).bytes);
        assert!(Path::new(&c.root).join("trophies/NPWR03760_00.json").is_file());
        assert!(!Path::new(&c.root).join("dev_hdd0/disc").exists(), "only the saves and trophies are copied");
        assert!(!s.stage_of("Cópia-1").exists());

        // the list hides a stage left by a crash
        fs::create_dir_all(s.stage_of("meio")).unwrap();
        assert!(!list(&s).iter().any(|p| p.name.contains("meio")));

        assert!(delete(&s, &c.id, "errado").is_err());
        delete(&s, &c.id, &c.name).unwrap();
        assert!(!Path::new(&c.root).exists());
        assert!(savedata_of(&builtin).join("BLUS31029EEDIT/DATA.BIN").is_file(), "the source stays");
        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_symlink_in_profiles_is_not_followed_on_delete() {
        let (root, s) = store("symlink");
        let outside = root.join("outside");
        fs::create_dir_all(&outside).unwrap();
        fs::write(outside.join("keep"), "x").unwrap();
        fs::create_dir_all(s.dir()).unwrap();
        std::os::unix::fs::symlink(&outside, s.dir().join("link")).unwrap();
        // not listed as a profile, since it is not a real folder
        assert!(resolve(&s, "local:link").is_err());
        assert!(delete(&s, "local:link", "link").is_err());
        assert!(outside.join("keep").is_file());
        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn external_folders_are_registered_never_changed() {
        let (root, s) = store("external");
        let ext = root.join("test-save/gamedata");
        put_save(&savedata_of(&ext), "BLUS31029EEDIT", 5, b"DATA.BIN\n");
        let before = usage(&savedata_of(&ext));

        let p = register_external(&s, "Flamengo", &ext).unwrap();
        assert_eq!((p.kind, p.read_only, p.id.as_str()), (Kind::External, true, "ext:Flamengo"));
        assert_eq!(resolve(&s, "ext:Flamengo").unwrap().root, ext.to_string_lossy());
        assert_eq!(usage(&savedata_of(&ext)), before);

        // the savedata folder itself registers its root
        let q = register_external(&s, "Outro", &savedata_of(&ext)).unwrap();
        assert_eq!(q.root, ext.to_string_lossy());

        for (name, path) in [
            ("a", PathBuf::from("relative/x")),
            ("b", root.join("test-save/../test-save/gamedata")),
            ("c", root.join("no-such-folder")),
            ("d", root.join("test-save")),
        ] {
            assert!(register_external(&s, name, &path).is_err(), "{}", path.display());
        }
        // the launcher's own keys folder cannot become a profile
        let keys = s.data.join("keys");
        put_save(&savedata_of(&keys), "BLUS31029EEDIT", 1, b"");
        assert!(register_external(&s, "k", &keys).is_err());
        // nor can padrão be registered a second time
        fs::create_dir_all(savedata_of(s.builtin_root.as_ref().unwrap())).unwrap();
        assert!(register_external(&s, "p", s.builtin_root.as_ref().unwrap()).is_err());

        // forgetting it leaves its contents alone
        delete(&s, &p.id, &p.name).unwrap();
        assert!(resolve(&s, &p.id).is_err());
        assert_eq!(usage(&savedata_of(&ext)), before);
        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn install_source_is_checked() {
        let (root, _) = store("source");
        let console = vec![0xFFu8; 0x400];
        let ps3 = root.join("usb/PS3/SAVEDATA");
        put_save(&ps3, "BLUS31029EEDIT", 1, &console);
        assert_eq!(saves_source(&root.join("usb")).unwrap(), ps3);
        assert_eq!(saves_source(&ps3).unwrap(), ps3);
        assert!(saves_source(&root.join("nothing")).is_err());
        // already decrypted: the runtime's text list
        let done = root.join("done");
        put_save(&done, "BLUS31029EEDIT", 1, b"DATA.BIN\n");
        assert!(saves_source(&done).unwrap_err().contains("already decrypted"));
        // another game's saves do not count
        let other = root.join("other");
        put_save(&other, "BCES00001SAVE", 1, &console);
        assert!(saves_source(&other).is_err());
        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn edit_counts_from_the_tool() {
        let j = r#"{"players":[{"id":1},{"id":2}],"teams":[{"id":3}],"rosters":[]}"#;
        assert_eq!(parse_edit_json(j).unwrap(), EditCounts { players: 2, teams: 1, rosters: 0 });
        assert!(parse_edit_json("{}").is_err());
        assert!(parse_edit_json("not json").is_err());
    }

    #[test]
    fn nothing_here_reads_the_keys() {
        // the key file's path is built, never opened: a file there is unchanged
        // and a missing one is only "not there"
        let (root, s) = store("keys");
        assert!(!keys_file(&s.data).exists());
        fs::create_dir_all(s.data.join("keys")).unwrap();
        fs::write(keys_file(&s.data), "secret").unwrap();
        let p = create_empty(&s, "x").unwrap();
        assert!(!walk_names(Path::new(&p.root)).iter().any(|n| n.contains("keys")));
        fs::remove_dir_all(&root).unwrap();
    }

    fn walk_names(dir: &Path) -> Vec<String> {
        let mut out = Vec::new();
        for e in fs::read_dir(dir).into_iter().flatten().flatten() {
            out.push(e.file_name().to_string_lossy().into_owned());
            if e.path().is_dir() {
                out.extend(walk_names(&e.path()));
            }
        }
        out
    }
}
