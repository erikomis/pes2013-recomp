// The rebuild's progress, read from tools/rebuild.sh's output: each step starts
// with a "==> <step>" line (zsh's bold escapes stripped), the next one ends it,
// "==> done" ends the run. The weights are a step's rough share of a full
// rebuild (the lift and the compile dominate).

export const STEP_IDS = ["decrypt", "analyse", "lift", "spu", "build"] as const;
export type StepId = (typeof STEP_IDS)[number];
/** The steps Advanced > Install / rebuild lets the player pick. */
export const PICK_IDS: StepId[] = ["decrypt", "analyse", "lift", "spu", "build"];
const WEIGHT: Record<StepId, number> = { decrypt: 2, analyse: 6, lift: 35, spu: 6, build: 51 };

export interface Step {
  id: StepId;
  state: "pending" | "running" | "done" | "error" | "skipped";
  start: number;
  secs: number;
  /** The share done, when the step reports it ("==> [k/n]"). */
  sub?: number;
}

const ESC = /\x1b\[[0-9;]*[A-Za-z]/g;

export class RebuildProgress {
  steps: Step[] = [];
  log: string[] = [];
  cancelled = false;
  started = 0;
  /** "rebuild", or "pull" for Updates > Get the new sources (no steps). */
  kind: "rebuild" | "pull" = "rebuild";
  /** The "ERROR: ..." lines the scripts printed. */
  errors: string[] = [];

  reset(only: string[] = [], kind: "rebuild" | "pull" = "rebuild") {
    this.kind = kind;
    this.log = [];
    this.errors = [];
    this.cancelled = false;
    this.started = Date.now();
    const want = (id: StepId) => !only.length || only.includes(id);
    this.steps = kind === "pull" ? [] : STEP_IDS.filter(want).map((id) => ({ id, state: "pending", start: 0, secs: 0 }));
  }

  /** The step that is running, or the one that failed. */
  stage(): Step | undefined {
    return this.steps.find((s) => s.state === "running" || s.state === "error");
  }

  private current(): Step | undefined {
    return this.steps.find((s) => s.state === "running");
  }

  private close(state: Step["state"]) {
    const c = this.current();
    if (c) {
      c.state = state;
      c.secs = (Date.now() - c.start) / 1000;
    }
  }

  feed(raw: string) {
    const line = raw.replace(ESC, "");
    this.log.push(line);
    if (this.log.length > 20000) this.log.splice(0, this.log.length - 20000);
    if (line.startsWith("ERROR:")) this.errors.push(line.slice(6).trim());
    const k = line.match(/^==>\s+\[(\d+)\/(\d+)\]/);
    if (k) {
      const c = this.current();
      if (c) c.sub = (Number(k[1]) - 1) / Math.max(1, Number(k[2]));
      return;
    }
    const m = line.match(/^==>\s+([a-z]+)/);
    if (!m) return;
    const word = m[1];
    if (word === "done") {
      this.close("done");
      return;
    }
    const step = this.steps.find((s) => s.id === word);
    if (!step) return;
    this.close("done");
    // steps the script went past without a line of their own
    for (const s of this.steps) {
      if (s === step) break;
      if (s.state === "pending") s.state = "skipped";
    }
    step.state = "running";
    step.start = Date.now();
  }

  finish(ok: boolean) {
    this.close(ok ? "done" : "error");
    if (ok) for (const s of this.steps) if (s.state === "pending") s.state = "skipped";
  }

  fraction(): number {
    const total = this.steps.reduce((a, s) => a + WEIGHT[s.id], 0);
    if (!total) return 0;
    let done = 0;
    for (const s of this.steps) {
      if (s.state === "done" || s.state === "skipped") done += WEIGHT[s.id];
      else if (s.state === "running") {
        // a running step counts as half done after its usual share of time,
        // or as far as it says it is
        const el = (Date.now() - s.start) / 1000;
        done += WEIGHT[s.id] * Math.max(s.sub ?? 0, Math.min(0.9, el / (el + 120)));
      }
    }
    return done / total;
  }

  /** Minutes left, from the time so far and the share done; null early on. */
  etaMinutes(): number | null {
    const f = this.fraction();
    const el = (Date.now() - this.started) / 60000;
    if (f < 0.05 || el < 0.5) return null;
    return (el / f) * (1 - f);
  }
}
