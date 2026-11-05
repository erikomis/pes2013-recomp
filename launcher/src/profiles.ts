// Option File page: the profiles (src-tauri/src/profiles.rs). Each is a
// PS3_GAMEDATA_ROOT: the built-in "padrão" (<port>/rpcs3), the ones made here
// (<data>/profiles/<name>) and folders registered without copying. Play passes
// the active one. Switching and every change are refused while the game runs.
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ask, open, save } from "@tauri-apps/plugin-dialog";
import { Key, lang, t } from "./i18n";
import { human } from "./ui";

interface EditCounts {
  players: number;
  teams: number;
  rosters: number;
}
interface Profile {
  id: string;
  name: string;
  kind: "builtin" | "local" | "external";
  root: string;
  savedata: string;
  readOnly: boolean;
  exists: boolean;
  saves: number;
  bytes: number;
  hasEdit: boolean;
  edit: EditCounts | null;
  editError: string | null;
  active: boolean;
}
interface View {
  profiles: Profile[];
  active: string;
  gameRunning: boolean;
  busy: boolean;
  keys: boolean;
  python: boolean;
}

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const tilde = (p: string) => p.replace(/^\/Users\/[^/]+/, "~");

let view: View | null = null;
let installing = false;
let working = false;
let opts: { changed: () => void | Promise<void>; setActive: (id: string) => void };

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text = ""): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

const locked = () => !view || view.gameRunning || view.busy || working || installing;

export async function refreshProfiles() {
  try {
    view = await invoke<View>("profiles_list");
  } catch (e) {
    $("pf-msg").textContent = String(e);
  }
  renderProfiles();
}

async function run<T>(msgId: string, what: () => Promise<T>, done: (r: T) => string) {
  if (working) return;
  working = true;
  renderProfiles();
  const msg = $(msgId);
  msg.textContent = t("pf.working");
  try {
    msg.textContent = done(await what());
  } catch (e) {
    msg.textContent = String(e);
  }
  working = false;
  await refreshProfiles();
  await opts.changed();
}

function card(p: Profile): HTMLElement {
  const c = el("div", "pf-card" + (p.active ? " active" : ""));
  const head = el("div", "row pf-head");
  head.append(el("strong", "", p.name));
  head.append(el("span", "pill muted-pill", t(`pf.kind.${p.kind}` as Key)));
  if (p.active) head.append(el("span", "pill accent", t("pf.active")));
  if (!p.exists) head.append(el("span", "pill bad", t("pf.missing")));
  c.append(head);

  const nf = new Intl.NumberFormat(lang());
  const facts: string[] = [t("pf.saves", { n: nf.format(p.saves), size: human(p.bytes) })];
  if (p.edit) facts.push(t("pf.edit", { teams: nf.format(p.edit.teams), players: nf.format(p.edit.players) }));
  else if (p.hasEdit) facts.push(t("pf.editUnread"));
  else facts.push(t("pf.noEdit"));
  c.append(el("div", "small", facts.join(" · ")));
  if (p.editError) c.append(el("div", "small hint-warn", p.editError));
  const path = el("div", "small muted", tilde(p.root));
  path.title = p.root;
  c.append(path);

  const act = el("div", "row pf-actions");
  const b = (label: string, fn: () => void, cls = "", disabled = locked()) => {
    const x = el("button", cls, label);
    x.disabled = disabled;
    x.addEventListener("click", fn);
    act.append(x);
  };
  if (!p.active) {
    b(t("pf.use"), () =>
      run("pf-msg", async () => {
        await invoke("profile_set_active", { id: p.id });
        opts.setActive(p.id);
      }, () => t("pf.switched", { name: p.name })), "primary", locked() || !p.exists);
  }
  b(t("saves.exportZip"), async () => {
    const dest = await save({ title: t("saves.exportZip"), defaultPath: `pes2013-${p.name}.zip`, filters: [{ name: "ZIP", extensions: ["zip"] }] });
    if (dest) run("pf-msg", () => invoke<string>("profile_export_zip", { id: p.id, dest }), (r) => t("saves.exported", { path: tilde(r) }));
  }, "", locked() || !p.saves);
  if (p.kind === "local") {
    b(t("saves.importZip"), async () => {
      const zip = await open({ title: t("saves.importZip"), filters: [{ name: "ZIP", extensions: ["zip"] }] });
      if (typeof zip !== "string") return;
      if (!(await ask(t("pf.importAsk", { name: p.name }), { title: t("saves.importZip"), kind: "warning" }))) return;
      run("pf-msg", () => invoke<{ slots: string[] }>("profile_import_zip", { id: p.id, path: zip }), (r) => t("saves.imported", { n: r.slots.length }));
    });
  }
  b(t("pf.show"), () => invoke("reveal", { path: p.savedata }), "link", false);
  if (p.kind !== "builtin") {
    b(t(p.kind === "local" ? "pf.delete" : "pf.forget"), async () => {
      const yes = await ask(t(p.kind === "local" ? "pf.deleteAsk" : "pf.forgetAsk", { name: p.name, size: human(p.bytes), path: tilde(p.root) }), {
        title: t(p.kind === "local" ? "pf.delete" : "pf.forget"),
        kind: "warning",
      });
      if (yes) run("pf-msg", () => invoke("profile_delete", { id: p.id, confirm: p.name }), () => t("pf.deleted", { name: p.name }));
    }, "link danger-link");
  }
  c.append(act);
  return c;
}

const KIND_HINT: Record<string, Key> = {
  empty: "pf.hintEmpty",
  copy: "pf.hintCopy",
  folder: "pf.hintFolder",
  zip: "pf.hintZip",
};

export function renderProfiles() {
  if (!opts) return;
  const v = view;
  $("pf-busy").classList.toggle("hidden", !v?.gameRunning);
  const list = $("pf-list");
  list.replaceChildren(...(v ? v.profiles.map(card) : []));

  const kind = $<HTMLSelectElement>("pf-kind").value;
  $("pf-kind-hint").textContent = t(KIND_HINT[kind] ?? "pf.hintEmpty");
  $("pf-from-row").classList.toggle("hidden", kind !== "copy");
  $("pf-path-row").classList.toggle("hidden", kind !== "folder" && kind !== "zip");
  const sel = $<HTMLSelectElement>("pf-from");
  const keep = sel.value;
  sel.replaceChildren(...(v?.profiles ?? []).filter((p) => p.exists).map((p) => new Option(`${p.name} (${human(p.bytes)})`, p.id)));
  if ([...sel.options].some((o) => o.value === keep)) sel.value = keep;

  const create = $<HTMLButtonElement>("pf-create");
  create.disabled = locked() || (kind === "folder" && (!v?.keys || !v?.python));
  const note = $("pf-create-msg");
  if (kind === "folder" && v && !installing && !working) {
    note.textContent = !v.keys ? t("pf.noKeys") : !v.python ? t("pf.noPython") : note.textContent === t("pf.noKeys") || note.textContent === t("pf.noPython") ? "" : note.textContent;
  }
  $("pf-cancel").classList.toggle("hidden", !installing);
  $<HTMLButtonElement>("pf-ext-add").disabled = locked();
}

async function createProfile() {
  const name = $<HTMLInputElement>("pf-name").value.trim();
  const kind = $<HTMLSelectElement>("pf-kind").value;
  const path = $<HTMLInputElement>("pf-path").value.trim();
  const msg = $("pf-create-msg");
  if (!name) {
    msg.textContent = t("pf.needName");
    return;
  }
  if ((kind === "folder" || kind === "zip") && !path) {
    msg.textContent = t("pf.needSource");
    return;
  }
  if (kind === "folder") {
    const log = $("pf-log");
    log.textContent = "";
    log.classList.remove("hidden");
    msg.textContent = t("pf.installing");
    installing = true;
    renderProfiles();
    try {
      await invoke("profile_install", { name, path });
    } catch (e) {
      installing = false;
      msg.textContent = String(e);
      renderProfiles();
    }
    return;
  }
  const from = kind === "copy" ? $<HTMLSelectElement>("pf-from").value : null;
  await run("pf-create-msg", () => invoke<{ name: string }>("profile_create", { req: { name, kind, from, path: kind === "zip" ? path : null } }), (p) => {
    $<HTMLInputElement>("pf-name").value = "";
    $<HTMLInputElement>("pf-path").value = "";
    return t("pf.created", { name: p.name });
  });
}

export function initProfiles(o: typeof opts) {
  opts = o;
  $("pf-refresh").addEventListener("click", refreshProfiles);
  $("pf-kind").addEventListener("change", () => {
    $("pf-create-msg").textContent = "";
    $<HTMLInputElement>("pf-path").value = "";
    renderProfiles();
  });
  $("pf-path-pick").addEventListener("click", async () => {
    const kind = $<HTMLSelectElement>("pf-kind").value;
    const p = kind === "zip" ? await open({ title: t("pf.kindZip"), filters: [{ name: "ZIP", extensions: ["zip"] }] }) : await open({ directory: true, title: t("pf.kindFolder") });
    if (typeof p === "string") $<HTMLInputElement>("pf-path").value = p;
  });
  $("pf-create").addEventListener("click", createProfile);
  $("pf-cancel").addEventListener("click", () => invoke("profile_cancel"));
  $("pf-ext-pick").addEventListener("click", async () => {
    const p = await open({ directory: true, title: t("pf.register") });
    if (typeof p === "string") $<HTMLInputElement>("pf-ext-path").value = p;
  });
  $("pf-ext-add").addEventListener("click", () => {
    const name = $<HTMLInputElement>("pf-ext-name").value.trim();
    const path = $<HTMLInputElement>("pf-ext-path").value.trim();
    if (!name || !path) {
      $("pf-ext-msg").textContent = t(!name ? "pf.needName" : "pf.needSource");
      return;
    }
    run("pf-ext-msg", () => invoke<{ name: string }>("profile_register", { name, path }), (p) => {
      $<HTMLInputElement>("pf-ext-name").value = "";
      $<HTMLInputElement>("pf-ext-path").value = "";
      return t("pf.registered", { name: p.name });
    });
  });
  listen<string>("profile-line", (ev) => {
    const log = $("pf-log");
    log.textContent += ev.payload + "\n";
    log.scrollTop = log.scrollHeight;
  });
  listen<{ ok: boolean; id: string | null; error: string | null }>("profile-exit", async (ev) => {
    installing = false;
    $("pf-create-msg").textContent = ev.payload.ok ? t("pf.installed") : t("pf.installFailed", { e: ev.payload.error ?? "" });
    if (ev.payload.ok) {
      $<HTMLInputElement>("pf-name").value = "";
      $<HTMLInputElement>("pf-path").value = "";
    }
    await refreshProfiles();
    await opts.changed();
  });
}
