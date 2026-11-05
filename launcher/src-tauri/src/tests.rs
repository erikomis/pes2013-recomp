use super::*;

fn tmp(tag: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("pes-launcher-{tag}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&d);
    fs::create_dir_all(&d).unwrap();
    d.canonicalize().unwrap()
}

fn all_features() -> Features {
    FEATURE_MARKERS.iter().map(|m| m.to_string()).collect()
}

/// What the build at build/BLUS31029/PES2013Recomp reads today.
fn todays_features() -> Features {
    [
        "PS3_LANG", "PS3_AA", "PS3_SHARPEN", "PS3_ANISO", "PS3_DISPLAY_GAMMA", "PS3_INPUT_MAP", "PS3_INPUT_MODE", "PS3_MOUSE", "PS3_MOUSE_SENS",
        "PS3_MOUSE_INVERT_X", "PS3_MOUSE_INVERT_Y", "PS3_MOUSE_DEADZONE", "PS3_MOUSE_CAPTURE", "PS3_RUMBLE", "PS3_RUMBLE_STRENGTH", "PS3_PAD_LOG",
        "PS3RECOMP_METAL_FPS", "PS3_VERBOSE", "PS3_NO_AUDIO", "PS3_FRAMECLOCK_US", "PS3_VBLANK_US", "PS3_QOS", "GCM_PUT_DOORBELL", "RSX_PACE_LOG", "AUDIO_ELASTIC",
    ]
    .iter()
    .map(|m| m.to_string())
    .collect()
}

fn env_of(s: &Settings, input: &InputEnv, features: &Features) -> BTreeMap<String, String> {
    launch_env(s, Path::new("/port"), Path::new("/port/rpcs3"), None, input, features).into_iter().collect()
}

#[test]
fn base64_matches_rfc4648() {
    assert_eq!(base64(b""), "");
    assert_eq!(base64(b"f"), "Zg==");
    assert_eq!(base64(b"foobar"), "Zm9vYmFy");
}

#[test]
fn env_lines() {
    let v = parse_env_lines("# c\nA=1\nexport B=\"x y\"\nbad key=2\n\nC=");
    assert_eq!(v, vec![("A".into(), "1".into()), ("B".into(), "x y".into()), ("C".into(), "".into())]);
}

#[test]
fn plist_values() {
    let xml = "<dict><key>image-path</key>\n\t<string>/a/b &amp; c.iso</string><key>system-entities</key><array>\
               <dict><key>mount-point</key><string>/Users/x/mnt_pes13</string></dict></array></dict>";
    assert_eq!(plist_strings(xml, "image-path"), vec!["/a/b & c.iso".to_string()]);
    assert_eq!(plist_strings(xml, "mount-point"), vec!["/Users/x/mnt_pes13".to_string()]);
}

#[test]
fn builds_and_argv() {
    let root = tmp("builds");
    let b = resolve_builds(&root);
    assert!(!b.ok && b.missing.len() == 3 && b.rebuild_sh.is_none());
    assert!(launch_argv(&Settings::default(), &b).is_err());
    for f in ["build/BLUS31029/PES2013Recomp", "game/EBOOT.elf", "tools/run.sh"] {
        let p = root.join(f);
        fs::create_dir_all(p.parent().unwrap()).unwrap();
        fs::write(p, b"x").unwrap();
    }
    let b = resolve_builds(&root);
    assert!(b.ok, "{:?}", b.missing);

    // Play is tools/run.sh; there is no window host and no --size
    let mut st = Settings::default();
    st.keep_awake = false;
    st.window_size = "1920x1080".into();
    let argv = launch_argv(&st, &b).unwrap();
    assert_eq!(argv, vec!["/bin/zsh".to_string(), s(&root.join("tools/run.sh"))]);
    st.keep_awake = true;
    let argv = launch_argv(&st, &b).unwrap();
    if Path::new("/usr/bin/caffeinate").is_file() {
        assert_eq!(&argv[..3], &["/usr/bin/caffeinate".to_string(), "-i".into(), "/bin/zsh".into()]);
    }
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn disc_layout_and_iso() {
    let root = tmp("disc");
    let disc = root.join("disc");
    fs::create_dir_all(disc.join("PS3_GAME")).unwrap();
    assert!(disc_root_of(&disc).is_none());
    fs::write(disc.join("PS3_GAME/PARAM.SFO"), saves::psf_write(&[])).unwrap();
    assert_eq!(disc_root_of(&disc), Some(disc.clone()));
    assert_eq!(disc_root_of(&disc.join("PS3_GAME")), Some(disc.clone()));
    assert!(disc_title_id(&disc).is_none());

    // what run.sh's *.iso(N) would pick, read through the symlink
    assert!(port_iso(&root).is_none());
    let downloads = root.join("elsewhere");
    fs::create_dir_all(&downloads).unwrap();
    std::os::unix::fs::symlink(&downloads, root.join("game_iso")).unwrap();
    fs::write(downloads.join("README.TXT"), "x").unwrap();
    assert!(port_iso(&root).is_none());
    fs::write(downloads.join("b.iso"), "x").unwrap();
    fs::write(downloads.join("a.iso"), "x").unwrap();
    assert_eq!(port_iso(&root).unwrap().file_name().unwrap(), "a.iso");

    // a disc that is not run.sh's own mount point is passed along
    assert_eq!(mount_override(Some(&disc)), Some(disc.clone()));
    assert_eq!(mount_override(Some(&default_mount())), None);
    assert_eq!(mount_override(None), None);

    assert!(data_pack(&root).is_none());
    fs::create_dir_all(root.join("BLUS31029_DOWNLOAD/USRDIR")).unwrap();
    assert_eq!(data_pack(&root), Some(root.join("BLUS31029_DOWNLOAD")));
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn logs_rotate_and_get_stamped() {
    let d = tmp("logs");
    let logs = d.join("logs");
    let log = d.join("last.log");
    // an empty or missing log is not kept
    assert!(rotate_log(&log, &logs, 3).is_none());
    fs::write(&log, "").unwrap();
    assert!(rotate_log(&log, &logs, 3).is_none());
    for n in 0..5 {
        fs::write(&log, format!("session {n}\n")).unwrap();
        let f = fs::OpenOptions::new().write(true).open(&log).unwrap();
        f.set_modified(UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000 + n * 60)).unwrap();
        drop(f);
        let to = rotate_log(&log, &logs, 3).unwrap();
        assert!(to.file_name().unwrap().to_string_lossy().starts_with("session-") && !log.exists());
    }
    let mut kept: Vec<String> = fs::read_dir(&logs).unwrap().flatten().map(|e| fs::read_to_string(e.path()).unwrap()).collect();
    kept.sort();
    assert_eq!(kept, ["session 2\n", "session 3\n", "session 4\n"]);

    // the stamper: every line, a partial last one too, then the raw file goes
    let raw = d.join("last.log.raw");
    fs::write(&raw, "one\ntwo\nthree").unwrap();
    let done = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
    stamp_log(raw.clone(), fs::File::create(&log).unwrap(), std::time::Instant::now(), done);
    let text = fs::read_to_string(&log).unwrap();
    let lines: Vec<&str> = text.lines().collect();
    assert_eq!(lines.len(), 3, "{text}");
    assert!(lines[0].starts_with("[    0.") && lines[0].ends_with("] one"), "{text}");
    assert!(lines[2].ends_with("] three"));
    assert!(!raw.exists());
    assert_eq!(report::strip_stamp(lines[1]), "two");
    fs::remove_dir_all(&d).unwrap();
}

/// With the defaults, Play adds only the folders to what run.sh does itself.
#[test]
fn defaults_are_run_sh() {
    let e = env_of(&Settings::default(), &InputEnv::default(), &all_features());
    let keys: Vec<&str> = e.keys().map(String::as_str).filter(|k| !k.starts_with("PS3RECOMP_FFMPEG_")).collect();
    assert_eq!(keys, ["PES_ROOT", "PS3_GAMEDATA_ROOT"]);
    assert_eq!(e["PES_ROOT"], "/port");
    assert_eq!(e["PS3_GAMEDATA_ROOT"], "/port/rpcs3");
    // and with this build's variables, nothing about FFmpeg either
    let e = env_of(&Settings::default(), &InputEnv::default(), &todays_features());
    assert_eq!(e.keys().map(String::as_str).collect::<Vec<_>>(), ["PES_ROOT", "PS3_GAMEDATA_ROOT"]);
}

#[test]
fn profile_and_disc_reach_the_environment() {
    let st = Settings::default();
    let v = launch_env(&st, Path::new("/p"), Path::new("/data/profiles/Brasil 2026"), Some(Path::new("/Volumes/PES")), &InputEnv::default(), &todays_features());
    let e: BTreeMap<String, String> = v.into_iter().collect();
    assert_eq!(e["PS3_GAMEDATA_ROOT"], "/data/profiles/Brasil 2026");
    assert_eq!(e["PES_MOUNT"], "/Volumes/PES");
}

/// Everything changed, against a build with every marker.
#[test]
fn launch_env_maps_the_settings() {
    let mut st = Settings::default();
    st.game_lang = "pt-br".into();
    st.aa = "smaa".into();
    st.sharpen = 0.3;
    st.aniso = 0;
    st.gamma_override = true;
    st.gamma = 1.1;
    st.vibrance = -0.25;
    st.contrast = 1.2;
    st.shadows = 0.1;
    st.midtones = -0.2;
    st.highlights = 0.3;
    st.clarity = 0.4;
    st.vignette = 0.5;
    st.grain = 0.1;
    st.lut_path = "/luts/warm.png".into();
    st.lut_preset = "film".into();
    st.lut_strength = 0.6;
    st.res_scale = "1.5".into();
    st.aspect = "21:9".into();
    st.mods = vec!["HD UI".into(), "a,b".into()];
    st.mods_dump = true;
    st.window_mode = "borderless".into();
    st.window_size = "1920x1080".into();
    st.display = "DELL U2720Q".into();
    st.vsync = false;
    st.upscale = "metalfx".into();
    st.input_mode = "keyboard".into();
    st.mouse_sens = 1.5;
    st.mouse_invert_y = true;
    st.mouse_deadzone = 10;
    st.mouse_capture = false;
    st.rumble_strength = 150;
    st.audio_volume = 40;
    st.audio_device = "AirPods".into();
    st.audio_elastic = false;
    st.show_fps = true;
    st.pad_log = true;
    st.telemetry = true;
    st.drain_spike_ms = 100;
    st.vcache_stats = true;
    st.pace_log_s = 5;
    st.shader_cache = true;
    st.shader_async = true;
    st.shader_async_jobs = 2;
    st.shader_sync_hit = 0;
    st.vertex_cache_split = false;
    st.bind_changed_only = false;
    st.frame_clock_us = 250;
    st.vblank_us = 16667;
    st.qos = false;
    st.put_doorbell = false;
    st.verbose_log = true;
    st.video = false;
    let input = InputEnv { path: Some("/data/input.toml".into()), has_mouse_section: false };
    let e = env_of(&st, &input, &all_features());
    for (k, v) in [
        ("PS3_LANG", "pt-br"),
        ("PS3_AA", "smaa"),
        ("PS3_SHARPEN", "0.30"),
        ("PS3_ANISO", "0"),
        ("PS3_DISPLAY_GAMMA", "1.10"),
        ("PS3_VIBRANCE", "-0.25"),
        ("PS3_CONTRAST", "1.20"),
        ("PS3_SHADOWS", "0.10"),
        ("PS3_MIDTONES", "-0.20"),
        ("PS3_HIGHLIGHTS", "0.30"),
        ("PS3_CLARITY", "0.40"),
        ("PS3_VIGNETTE", "0.50"),
        ("PS3_GRAIN", "0.10"),
        ("PS3_LUT", "/luts/warm.png"),
        ("PS3_LUT_PRESET", "film"),
        ("PS3_LUT_STRENGTH", "0.60"),
        ("PS3_RES_SCALE", "1.5"),
        ("PS3_ASPECT", "21:9"),
        ("PS3_MODS", "HD UI"),
        ("PS3_WINDOW_MODE", "borderless"),
        ("PS3_WINDOW_SIZE", "1920x1080"),
        ("PS3_DISPLAY", "DELL U2720Q"),
        ("PS3_VSYNC", "0"),
        ("PS3_UPSCALE", "metalfx"),
        ("PS3_INPUT_MAP", "/data/input.toml"),
        ("PS3_INPUT_MODE", "keyboard"),
        ("PS3_MOUSE_SENS", "1.50"),
        ("PS3_MOUSE_INVERT_Y", "1"),
        ("PS3_MOUSE_DEADZONE", "10"),
        ("PS3_MOUSE_CAPTURE", "0"),
        ("PS3_RUMBLE_STRENGTH", "150"),
        ("PS3_AUDIO_VOLUME", "40"),
        ("PS3_AUDIO_DEVICE", "AirPods"),
        ("AUDIO_ELASTIC", "0"),
        ("PS3RECOMP_METAL_FPS", "1"),
        ("PS3_PAD_LOG", "1"),
        ("PS3_TELEMETRY", "1"),
        ("RSX_DRAIN_SPIKE_MS", "100"),
        ("PS3RECOMP_ENG_VCACHE_STATS", "1"),
        ("RSX_PACE_LOG", "5"),
        ("PS3_SHADER_ASYNC", "1"),
        ("PS3_SHADER_ASYNC_JOBS", "2"),
        ("PS3_SHADER_ASYNC_SYNC_HIT", "0"),
        ("PS3RECOMP_ENG_VCACHE_SPLIT", "0"),
        ("PS3RECOMP_METAL_BIND_ALL", "1"),
        ("PS3_FRAMECLOCK_US", "250"),
        ("PS3_VBLANK_US", "16667"),
        ("PS3_QOS", "0"),
        ("GCM_PUT_DOORBELL", "0"),
        ("PS3_VERBOSE", "1"),
        ("PS3RECOMP_FFMPEG", "0"),
    ] {
        assert_eq!(e.get(k).map(String::as_str), Some(v), "{k}");
    }
    assert!(e["PS3_MODS_DIR"].ends_with("pes13-recomp/mods"));
    assert!(e["PS3_MODS_DUMP"].ends_with("pes13-recomp/texture-dump"));
    assert!(e["PS3_SHADER_CACHE"].ends_with("pes13-recomp/shadercache"));

    // every variable the launcher sets is one the build is searched for, so
    // none can be passed to a build that does not read it
    for k in e.keys().filter(|k| !["PES_ROOT", "PS3_GAMEDATA_ROOT"].contains(&k.as_str())) {
        assert!(FEATURE_MARKERS.contains(&k.as_str()), "{k} is not a marker");
    }
    // ... and against today's build only what it reads goes through
    let e = env_of(&st, &input, &todays_features());
    for k in ["PS3_VIBRANCE", "PS3_WINDOW_MODE", "PS3_LUT", "PS3_ASPECT", "PS3_MODS", "PS3_MODS_DUMP", "PS3_SHADER_CACHE", "PS3_TELEMETRY", "PS3_AUDIO_VOLUME", "PS3RECOMP_FFMPEG", "PS3_AA"] {
        assert!(!e.contains_key(k), "{k} passed to a build that does not read it");
    }
    for k in ["PS3_SHARPEN", "PS3_ANISO", "PS3_INPUT_MAP", "PS3_RUMBLE_STRENGTH", "PS3_FRAMECLOCK_US", "PS3_QOS", "GCM_PUT_DOORBELL", "AUDIO_ELASTIC"] {
        assert!(e.contains_key(k), "{k}");
    }
}

/// FXAA is the only PS3_AA value this runtime knows.
#[test]
fn smaa_needs_the_build_to_have_it() {
    let mut st = Settings::default();
    st.aa = "smaa".into();
    assert!(!env_of(&st, &InputEnv::default(), &todays_features()).contains_key("PS3_AA"));
    st.aa = "fxaa".into();
    assert_eq!(env_of(&st, &InputEnv::default(), &todays_features())["PS3_AA"], "fxaa");
    st.aa = "msaa".into();
    assert!(!env_of(&st, &InputEnv::default(), &all_features()).contains_key("PS3_AA"));
}

/// Mute goes through the best variable the build has, and only when on: the
/// runtime turns on at any value of these.
#[test]
fn mute_wiring() {
    let mut st = Settings::default();
    let vars = ["PS3_AUDIO_MUTE", "PS3_MUTE", "PS3_NO_AUDIO"];
    let has = |e: &BTreeMap<String, String>| -> Vec<&str> { vars.iter().copied().filter(|k| e.contains_key(*k)).collect() };
    assert!(has(&env_of(&st, &InputEnv::default(), &all_features())).is_empty(), "off passes none");
    st.audio_mute = true;
    st.audio_volume = 40;
    let e = env_of(&st, &InputEnv::default(), &todays_features());
    assert_eq!(has(&e), ["PS3_NO_AUDIO"], "today's macOS build has only this one");
    assert!(!e.contains_key("PS3_AUDIO_VOLUME"));
    let mut f = todays_features();
    f.insert("PS3_MUTE".into());
    assert_eq!(has(&env_of(&st, &InputEnv::default(), &f)), ["PS3_MUTE"], "a true mute is preferred");
    f.insert("PS3_AUDIO_MUTE".into());
    assert_eq!(has(&env_of(&st, &InputEnv::default(), &f)), ["PS3_AUDIO_MUTE"]);
    assert_eq!(mute_var(&Features::new()), None);
    assert!(has(&env_of(&st, &InputEnv::default(), &Features::new())).is_empty());
}

#[test]
fn values_that_change_nothing_or_are_invalid_stay_out() {
    let mut st = Settings::default();
    let f = all_features();
    st.frame_clock_us = FRAME_CLOCK_DEFAULT;
    st.vblank_us = VBLANK_DEFAULT;
    st.aniso = ANISO_DEFAULT;
    st.window_mode = "windowed".into();
    st.input_mode = "both".into();
    st.res_scale = "1".into();
    st.aspect = "16:9".into();
    st.display = "a\nb".into();
    st.lut_strength = 0.5; // no LUT: no strength either
    st.lut_preset = "sepia".into();
    st.window_size = "10x10".into();
    st.game_lang = "x; rm".into();
    let e = env_of(&st, &InputEnv::default(), &f);
    for k in ["PS3_FRAMECLOCK_US", "PS3_VBLANK_US", "PS3_ANISO", "PS3_WINDOW_MODE", "PS3_INPUT_MODE", "PS3_RES_SCALE", "PS3_ASPECT", "PS3_DISPLAY", "PS3_LUT_STRENGTH", "PS3_LUT_PRESET", "PS3_WINDOW_SIZE", "PS3_LANG", "PS3_INPUT_MAP"] {
        assert!(!e.contains_key(k), "{k}");
    }
    // the extra variables are passed as typed, last, and win
    st.extra_env = "PS3_ANISO=2\nX=y".into();
    let v = launch_env(&st, Path::new("/p"), Path::new("/g"), None, &InputEnv::default(), &Features::new());
    assert_eq!(v.iter().rev().find(|(k, _)| k == "PS3_ANISO").map(|(_, x)| x.as_str()), Some("2"));
    assert!(v.iter().any(|(k, x)| k == "X" && x == "y"));
    // a hand-written [mouse] in the file: every mouse setting is passed
    let st = Settings::default();
    let e = env_of(&st, &InputEnv { path: Some("/x.toml".into()), has_mouse_section: true }, &f);
    assert_eq!(e["PS3_MOUSE"], "1");
    assert_eq!(e["PS3_MOUSE_SENS"], "1.00");
    assert_eq!(e["PS3_MOUSE_DEADZONE"], "30");
    assert_eq!(e["PS3_MOUSE_CAPTURE"], "1");
    let mut st = Settings::default();
    st.mouse = false;
    st.rumble = false;
    let e = env_of(&st, &InputEnv::default(), &f);
    assert_eq!(e["PS3_MOUSE"], "0");
    assert!(!e.contains_key("PS3_MOUSE_SENS"));
    assert_eq!(e["PS3_RUMBLE"], "0");
}

#[test]
fn res_scale_values() {
    assert_eq!(res_scale_value(""), None);
    assert_eq!(res_scale_value("1"), None);
    assert_eq!(res_scale_value("1.5").as_deref(), Some("1.5"));
    assert_eq!(res_scale_value("2.6").as_deref(), Some("2.5"));
    assert_eq!(res_scale_value("5"), None);
    assert_eq!(res_scale_value("1080p"), None);
    assert_eq!(aspect_value(" 32:9 ").as_deref(), Some("32:9"));
    assert_eq!(aspect_value(""), None);
}

/// A launcher.json missing fields loads with their defaults, keeps its own, and
/// ignores what it does not know.
#[test]
fn old_settings_files_still_load() {
    let st: Settings = serde_json::from_str(r#"{"portDir": "/x", "aa": "fxaa", "campaign": "auto", "playDir": "/p"}"#).unwrap();
    assert_eq!(st.port_dir, "/x");
    assert_eq!(st.aa, "fxaa");
    assert_eq!(st.window_mode, "windowed");
    assert_eq!(st.active_profile, profiles::BUILTIN_ID);
    assert_eq!((st.aniso, st.frame_clock_us, st.vblank_us, st.save_backups_keep), (16, 1000, 16683, 0));
    assert!(st.qos && st.put_doorbell && st.audio_elastic && !st.show_fps && !st.verbose_log);
}

#[test]
fn input_map_file_is_written_and_kept() {
    let d = tmp("input");
    let p = d.join("sub/input.toml");
    let mut b = Bindings::default();
    b.keyboard.insert("r1".into(), vec!["X".into()]);
    b.keyboard.insert("cross".into(), vec!["Space".into()]);
    b.keyboard.insert("l3".into(), vec![]);
    b.mouse_buttons.insert("r1".into(), vec!["Left".into()]);
    b.mouse_buttons.insert("triangle".into(), vec!["WheelUp".into(), "WheelDown".into()]);
    b.controller.insert("cross".into(), vec!["a".into()]);
    write_input_map(&p, b.clone()).unwrap();
    let text = fs::read_to_string(&p).unwrap();
    assert!(text.starts_with("# PES 2013 recomp: controls"));
    assert!(text.contains("[keyboard]\ncross    = \"Space\"\n"));
    assert!(text.contains("l3       = \"\"\n"));
    assert!(text.contains("[mouse_buttons]\ntriangle = \"WheelUp, WheelDown\"\nr1       = \"Left\"\n"));
    assert!(text.contains("[controller]\ncross    = \"a\"\n"));
    assert_eq!(input_map::parse(&text).bindings, b);
    // a hand-written [mouse] survives the next save
    fs::write(&p, format!("{text}\n[mouse]\nsensitivity = 2.0\n")).unwrap();
    b.keyboard.insert("r1".into(), vec!["F".into()]);
    write_input_map(&p, b.clone()).unwrap();
    let f = input_map::parse(&fs::read_to_string(&p).unwrap());
    assert_eq!(f.bindings.keyboard["r1"], vec!["F"]);
    assert!(f.has_mouse_section && f.other.contains("sensitivity = 2.0"));
    // names that could break the file are refused, and the file stays
    b.keyboard.insert("cross".into(), vec!["Q\"\n[x]".into()]);
    assert!(write_input_map(&p, b).is_err());
    assert_eq!(input_map::parse(&fs::read_to_string(&p).unwrap()).bindings.keyboard["cross"], vec!["Space"]);
    fs::remove_dir_all(&d).unwrap();
}

#[test]
fn feature_markers_in_a_build() {
    let d = tmp("features");
    let exe = d.join("game");
    fs::write(&exe, b"\x7fELF junk\0PS3_INPUT_MAP\0more PS3_TELEMETRY=%s\0 PS3_TELEMETRY\0 PS3_RES_SCALE_X\0XPS3_LUT\0PS3_LUT is the LUT\0smaa\0").unwrap();
    let b = Builds { eboot: Some(s(&exe)), ..Default::default() };
    let cache = Mutex::new(FeatureCache::new());
    let file = d.join("data/build-features.json");
    assert_eq!(build_features_in(&b, &cache, &file), vec!["PS3_INPUT_MAP".to_string(), "PS3_TELEMETRY".to_string(), "smaa".to_string()]);
    assert_eq!(cache.lock().unwrap().len(), 1);
    assert_eq!(build_features_in(&b, &cache, &file).len(), 3, "from the cache");
    // a new launcher run reads the file instead of scanning
    assert!(fs::read_to_string(&file).unwrap().contains("PS3_INPUT_MAP"));
    assert_eq!(build_features_in(&b, &Mutex::new(FeatureCache::new()), &file).len(), 3);
    assert!(build_features_in(&Builds::default(), &cache, &file).is_empty());

    // PS3_DISPLAY is not found in PS3_DISPLAY_GAMMA, nor PS3_MOUSE in its longer names
    let mut found = Features::new();
    markers_in(b"\0PS3_DISPLAY_GAMMA\0PS3_MOUSE_SENS\0", &mut found);
    assert_eq!(found.into_iter().collect::<Vec<_>>(), ["PS3_DISPLAY_GAMMA", "PS3_MOUSE_SENS"]);

    // a name across two of the pieces the file is read in
    let exe2 = d.join("big");
    let mut big = vec![1u8; (8 << 20) - 5];
    big.extend_from_slice(b"\0PS3_QOS\0");
    big.extend_from_slice(&[1u8; 4096]);
    fs::write(&exe2, &big).unwrap();
    assert!(scan_markers(&exe2).contains("PS3_QOS"));
    fs::remove_dir_all(&d).unwrap();
}

/// The marker list against the real binary, when it is there:
/// `cargo test -- --ignored real_build --nocapture`.
#[test]
#[ignore]
fn real_build_features() {
    let exe = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../build/BLUS31029/PES2013Recomp");
    let t = std::time::Instant::now();
    let found = scan_markers(&exe);
    println!("{:.1} s: {found:?}", t.elapsed().as_secs_f64());
    println!("not in the build: {:?}", FEATURE_MARKERS.iter().filter(|m| !found.contains(**m)).collect::<Vec<_>>());
    for m in todays_features() {
        assert!(found.contains(&m), "{m}");
    }
}

#[test]
fn screen_names() {
    assert_eq!(parse_screens("[\"Built-in Retina Display\",\"DELL U2720Q\"]\n"), vec!["Built-in Retina Display", "DELL U2720Q"]);
    assert!(parse_screens("oops").is_empty());
}

#[test]
fn window_sizes() {
    assert!(valid_window_size("1280x720"));
    assert!(valid_window_size("2560x1440"));
    assert!(!valid_window_size(""));
    assert!(!valid_window_size("10x10"));
    assert!(!valid_window_size("1280x720x1"));
}

#[test]
fn rebuild_script_steps() {
    assert_eq!(rebuild_script(&[]), "set -e\nexec tools/rebuild.sh decrypt analyse lift spu build\n");
    assert_eq!(rebuild_script(&["build".into()]), "set -e\nexec tools/rebuild.sh build\n");
    assert_eq!(rebuild_script(&["spu".into(), "lift".into()]), "set -e\nexec tools/rebuild.sh lift spu\n");
}

/// tools/pes2013_edit.py is called read-only and its refusals reach the page.
#[test]
fn edit_tool_refuses_a_file_it_does_not_know() {
    let tool = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tools/pes2013_edit.py");
    if !tool.is_file() || !Path::new("/usr/bin/python3").is_file() {
        return;
    }
    let d = tmp("edit-tool");
    let f = d.join("DATA.BIN");
    fs::write(&f, b"not an edit file").unwrap();
    let err = run_edit_tool(Path::new("/no/such/python"), &tool, &f).unwrap_err();
    assert!(err.contains("Unsupported"), "{err}");
    assert_eq!(fs::read(&f).unwrap(), b"not an edit file");
    fs::remove_dir_all(&d).unwrap();
}

/// The real Option File, read-only:
/// `cargo test -- --ignored real_edit --nocapture`.
#[test]
#[ignore]
fn real_edit_counts() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let f = root.join("rpcs3/dev_hdd0/home/00000001/savedata/BLUS31029EEDIT/DATA.BIN");
    let t = std::time::Instant::now();
    let c = run_edit_tool(&venv_python(&root), &root.join("tools/pes2013_edit.py"), &f).unwrap();
    println!("{:.2} s: {c:?}", t.elapsed().as_secs_f64());
    println!("usage: {:?}", profiles::usage(f.parent().unwrap().parent().unwrap()));
    let t = std::time::Instant::now();
    println!("newest: {:?} in {:.3} s", saves::newest_slot(f.parent().unwrap().parent().unwrap()).map(|s| s.name), t.elapsed().as_secs_f64());
}

/// tools/install_savedata.py into a temp folder, with made-up keys and a save
/// whose console PARAM.PFD protects nothing. Skipped where the venv is missing.
#[test]
fn install_tool_runs_into_a_stage() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let (py, tool) = (venv_python(&root), root.join("tools/install_savedata.py"));
    if !py.is_file() || !tool.is_file() {
        return;
    }
    let d = tmp("install-tool");
    let store = profiles::Store { data: d.join("data"), builtin_root: None };
    let src = d.join("usb/PS3/SAVEDATA");
    let save = src.join("BLUS31029EFACE001");
    fs::create_dir_all(&save).unwrap();
    fs::write(save.join("PARAM.SFO"), saves::psf_write(&[])).unwrap();
    let mut pfd = vec![0u8; 0x400];
    pfd[0] = 0xFF;
    fs::write(save.join("PARAM.PFD"), &pfd).unwrap();
    fs::write(save.join("DATA.BIN"), b"face").unwrap();
    fs::write(save.join("ICON0.png"), b"png").unwrap();
    let keys = d.join("keys.txt");
    fs::write(&keys, format!("syscon_manager_key={}\nsecure_file_id={}\n", "00".repeat(16), "11".repeat(16))).unwrap();

    let found = profiles::saves_source(&d.join("usb")).unwrap();
    assert_eq!(found, src);
    let (name, dst) = profiles::prepare_install(&store, "Do Pendrive").unwrap();
    let out = Command::new(&py).arg("-I").arg(&tool).arg(&found).arg(&dst).arg("--keys").arg(&keys).output().unwrap();
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    let p = profiles::commit(&store, &name).unwrap();
    let got = Path::new(&p.savedata).join("BLUS31029EFACE001");
    assert_eq!(fs::read(got.join("DATA.BIN")).unwrap(), b"face");
    assert!(got.join("ICON0.PNG").is_file(), "renamed for cellSaveData");
    assert_eq!(profiles::usage(Path::new(&p.savedata)).saves, 1);
    assert_eq!(fs::read(save.join("DATA.BIN")).unwrap(), b"face", "the source stays");
    fs::remove_dir_all(&d).unwrap();
}

/// A backup, a zip and a copy of a profile never carry the data folder's keys.
#[test]
fn keys_stay_out_of_backups_and_zips() {
    let d = tmp("no-keys");
    let data = d.join("data");
    fs::create_dir_all(data.join("keys")).unwrap();
    fs::write(data.join("keys/savedata_keys.txt"), "secure_file_id=SECRET").unwrap();
    let store = profiles::Store { data: data.clone(), builtin_root: Some(d.join("rpcs3")) };
    let saved = profiles::savedata_of(&d.join("rpcs3")).join("BLUS31029EEDIT");
    fs::create_dir_all(&saved).unwrap();
    fs::write(saved.join("PARAM.SFO"), saves::psf_write(&[])).unwrap();
    fs::write(saved.join("DATA.BIN"), b"edit").unwrap();
    let padrao = profiles::resolve(&store, "").unwrap();
    let copy = profiles::create_copy(&store, "c", &padrao).unwrap();
    let loc = saves::Locations { port_savedata: PathBuf::from(&copy.savedata), rpcs3_hdd0: d.join("none"), backups: data.join("save-backups/x") };
    saves::create_backup(&loc, Side::Port, "", None, "manual", 5).unwrap().unwrap();
    let zip = d.join("x.zip");
    saves::export_zip(&loc, None, &zip, 6).unwrap();
    let names: Vec<String> = zipfile::read(&zip, &saves::ZIP_LIMITS).unwrap().into_iter().map(|e| e.name).collect();
    assert!(names.iter().all(|n| !n.contains("keys")), "{names:?}");
    let mut seen = Vec::new();
    fn walk(p: &Path, out: &mut Vec<Vec<u8>>) {
        for e in fs::read_dir(p).into_iter().flatten().flatten() {
            if e.path().is_dir() {
                walk(&e.path(), out);
            } else {
                out.push(fs::read(e.path()).unwrap());
            }
        }
    }
    walk(Path::new(&copy.root), &mut seen);
    walk(&data.join("save-backups"), &mut seen);
    seen.push(fs::read(&zip).unwrap());
    assert!(seen.iter().all(|b| !b.windows(6).any(|w| w == b"SECRET")));
    fs::remove_dir_all(&d).unwrap();
}

#[test]
fn reveal_never_opens_an_app_bundle() {
    let tmp = std::env::temp_dir().join(format!("pes13-reveal-{}", std::process::id()));
    let app = tmp.join("Some.app");
    std::fs::create_dir_all(&app).unwrap();
    // A missing file inside a bundle selects the bundle instead of opening it.
    let (t, select) = crate::reveal_target(&app.join("missing/file.txt")).unwrap();
    assert_eq!(t, app);
    assert!(select);
    // The bundle itself is selected too.
    let (_, select) = crate::reveal_target(&app).unwrap();
    assert!(select);
    // A plain folder opens; a missing file in it opens that folder.
    let (t, select) = crate::reveal_target(&tmp.join("nope.log")).unwrap();
    assert_eq!(t, tmp);
    assert!(!select);
    assert!(crate::reveal_target(std::path::Path::new("relative/path")).is_err());
    std::fs::remove_dir_all(&tmp).unwrap();
}

/// A developer's checkout gets nothing extra; only the installed port has its
/// toolkit, venv and key file in the data folder.
#[test]
fn installed_port_environment() {
    let d = tmp("port-env");
    let st = Settings::default();
    assert!(port_env(&d, &st).is_empty());
    assert!(!is_installed_port(&d));
    let p = install_layout().port();
    assert!(is_installed_port(&p));
    let e: BTreeMap<String, String> = port_env(&p, &st).into_iter().collect();
    assert!(e["PS3RECOMP_DIR"].ends_with("pes13-recomp/toolkit"));
    assert!(e["PES_VENV"].ends_with("pes13-recomp/venv"));
    assert!(!e.contains_key("PES_KEYS"), "no key file chosen");
    assert_eq!(toolkit_dir(&p), install_layout().toolkit());
    assert_eq!(venv_python(&p), install_layout().venv().join("bin/python"));
    fs::remove_dir_all(&d).unwrap();
}
