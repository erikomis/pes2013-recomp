#!/usr/bin/env python3
"""Look up the 2026 squad players in pesdb.net's eFootball database.

    collect_pesdb_2026.py --squads squads.json [--squads more.json] --clubs clubs.json
                          --cache DIR --out pesdb_2026.json [--offline] [--delay 1.5]

Each squads file has {"clubs": [{"name" or "club_key", "athletes": [...]}]}
(analysis/brasil_2026_candidate_squads.json, analysis/competitions-2026/
squad_references.json). clubs.json is a list of {"squad": "<club_key or name>",
"slot": team id, "country": "BRA"}; the country stands in for a player's
nationality when the squad data has none. For each athlete of those squads this searches pesdb by name
(standard cards only), opens up to four candidates and keeps one only when it
is the same person: the nationality matches where both are known, the age
differs by at most one year from the 2026 birth date where it is known, and
every name on the card is in the player's full or shirt name, and the height is
within 3 cm of the 2026 data where both are known. Anything else is left unmatched
rather than guessed.

Every page is cached in DIR, so a rerun with --offline makes no requests. The
collector is sequential, waits longer after each HTTP 429, and stops after
three network errors in a row.
"""
import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.error
import urllib.request

BASE = "https://pesdb.net"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
STATS = ["Attacking Awareness", "Ball Control", "Dribbling", "Tight Possession", "Low Pass",
         "Lofted Pass", "Finishing", "Heading", "Set Piece Taking", "Curl", "Defensive Awareness",
         "Tackling", "Aggression", "Defensive Engagement", "GK Awareness", "GK Catching",
         "GK Parrying", "GK Reflexes", "GK Reach", "Speed", "Acceleration", "Kicking Power",
         "Jumping", "Physical Contact", "Balance", "Stamina"]
NATION = {"BRA": "Brazil", "ARG": "Argentina", "URU": "Uruguay", "PAR": "Paraguay", "CHI": "Chile",
          "COL": "Colombia", "ECU": "Ecuador", "PER": "Peru", "BOL": "Bolivia", "VEN": "Venezuela"}


def key(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())


class Fetcher:
    def __init__(self, cache, offline, delay):
        self.cache, self.offline, self.delay = Path(cache), offline, delay
        self.cache.mkdir(parents=True, exist_ok=True)
        self.errors = 0
        self.requests = 0

    def get(self, path):
        f = self.cache / (hashlib.sha256(path.encode()).hexdigest()[:24] + ".html")
        if f.exists():
            return f.read_text(encoding="utf-8", errors="replace")
        if self.offline:
            return None
        if self.errors >= 3:
            raise SystemExit("three network errors in a row; stopping (rerun to resume from the cache)")
        body = None
        for attempt in range(4):
            time.sleep(self.delay if attempt == 0 else 90 * attempt)
            try:
                req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
                body = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    self.errors += 1
                    print(f"  error {exc} for {path}", file=sys.stderr)
                    return None
                print(f"  429, waiting {90 * (attempt + 1)} s", file=sys.stderr, flush=True)
            except Exception as exc:  # noqa: BLE001 - any network failure counts
                self.errors += 1
                print(f"  error {exc} for {path}", file=sys.stderr)
                return None
        if body is None:
            self.errors += 1
            return None
        self.errors = 0
        self.requests += 1
        f.write_text(body, encoding="utf-8")
        return body


def search(fx, name):
    q = urllib.parse.urlencode({"name": name, "type": "standard"})
    page = fx.get(f"/efootball/players/?{q}")
    if not page:
        return []
    out = []
    for m in re.finditer(r'href="(/efootball/players/[a-z0-9-]+-(\d+))"[^>]*>\s*<img[^>]*alt="([^"]*)"', page):
        alt = html.unescape(m.group(3))
        n = re.match(r"(.*?) — ([A-Z]+), OVR (\d+)", alt)
        if n:
            out.append({"path": m.group(1), "id": m.group(2), "name": n.group(1), "pos": n.group(2),
                        "ovr": int(n.group(3))})
    return out


def detail(fx, path):
    page = fx.get(path)
    if not page:
        return None
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", t)))
    t = re.sub(r"(\|\s*)+", "|", t)

    def after(label, pat=r"([^|]+)"):
        m = re.search(r"\|" + re.escape(label) + r"\|" + pat, t)
        return m.group(1).strip() if m else None
    d = {"path": path, "stats": {}}
    for s in STATS:
        v = after(s, r"(\d+)")
        if v is not None:
            d["stats"][s] = int(v)
    d["nationality"] = after("Nationality")
    d["height"] = int(after("Height", r"(\d+)") or 0) or None
    d["weight"] = int(after("Weight", r"(\d+)") or 0) or None
    d["age"] = int(after("Age", r"(\d+)") or 0) or None
    d["foot"] = after("Stronger Foot")
    d["primary"] = after("Primary Position")
    sec = re.search(r"\|Secondary Positions\|(.*?)\|Player Details", t)
    d["secondary"] = [p for p in re.findall(r"\b(GK|CB|LB|RB|DMF|CMF|LMF|RMF|AMF|LWF|RWF|SS|CF)\b", sec.group(1))] if sec else []
    d["weak_foot_usage"] = after("Weak Foot Usage")
    d["weak_foot_accuracy"] = after("Weak Foot Accuracy")
    d["form"] = after("Form")
    d["injury_resistance"] = after("Injury Resistance")
    d["ovr"] = int(after("Overall Rating", r"(\d+)") or 0) or None
    d["name"] = after("Player Name")
    return d if len(d["stats"]) >= 20 else None


def age_on(birth, today):
    b = datetime.date.fromisoformat(birth)
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def athlete_info(a):
    """Name, shirt name, birth date and nationality from a squad_references athlete."""
    esp = (a.get("espn_candidates") or [{}])[0] if a.get("espn_candidates") else {}
    full = a.get("name") or esp.get("full_name") or a.get("display_name") or ""
    shirt = a.get("display_name") or ""
    birth = a.get("birth_date") or a.get("birth_date_proposal") or esp.get("birth_date")
    nat = esp.get("nationality") or a.get("nationality")
    return full, shirt, birth, nat


def height_cm(a):
    esp = (a.get("espn_candidates") or [{}])[0] if a.get("espn_candidates") else {}
    h = esp.get("height_inches") or a.get("height_inches")
    return round(float(h) * 2.54) if h else None


PARTICLES = {"de", "da", "do", "dos", "das", "del", "la", "e", "y", "van", "di"}


def names_ok(cand, full, shirt):
    """Every name in the card is in the player's full or shirt name; an initial
    matches the first letter of the full name; the shirt name is in the card."""
    ft, st = key(full).split(), key(shirt).split()
    words = set(ft) | set(st)
    ct = [t for t in re.sub(r"[^a-z. ]", " ", unicodedata.normalize("NFKD", cand).encode("ascii", "ignore").decode().lower()).split()]
    named = [t for t in ct if not t.endswith(".") and t not in PARTICLES]
    initials = [t[0] for t in ct if t.endswith(".")]
    if not named or any(t not in words for t in named):
        return False
    if initials and ft and ft[0][0] != initials[0]:
        return False
    return not st or any(t in named for t in st if t not in PARTICLES)


def match(fx, a, nation_hint, today):
    """The pesdb record of this athlete, or None when no candidate is clearly the same person."""
    full, shirt, birth, nat = athlete_info(a)
    want_age = age_on(birth, today) if birth else None
    if want_age is None and not nat:
        return None
    toks = key(full).split()
    queries = []
    for q in (shirt, " ".join(toks[-2:]) if len(toks) >= 2 else full, toks[-1] if toks else ""):
        q = q.strip()
        if q and len(q) >= 3 and q.lower() not in [x.lower() for x in queries]:
            queries.append(q)
    for q in queries:
        cands = [c for c in search(fx, q) if names_ok(c["name"], full, shirt)][:6]
        found = []
        for c in cands:
            d = detail(fx, c["path"])
            if not d or not names_ok(d.get("name") or c["name"], full, shirt):
                continue
            if nat and d.get("nationality") and key(nat) != key(d["nationality"]):
                continue
            if want_age is not None and (not d.get("age") or abs(d["age"] - want_age) > 1):
                continue
            h = height_cm(a)
            if h and d.get("height") and abs(d["height"] - h) > 3:
                continue
            found.append(d)
        if found:
            found.sort(key=lambda d: abs((d.get("age") or 0) - (want_age or 0)))
            return found[0]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--squads", required=True, action="append")
    ap.add_argument("--clubs", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--delay", type=float, default=1.5)
    a = ap.parse_args()
    by = {}
    for f in a.squads:
        for c in json.loads(Path(f).read_text(encoding="utf-8"))["clubs"]:
            if c.get("club_key"):
                by.setdefault(c["club_key"], c)
            by.setdefault(c["name"], c)
    clubs = json.loads(Path(a.clubs).read_text(encoding="utf-8"))
    fx = Fetcher(a.cache, a.offline, a.delay)
    today = datetime.date(2026, 11, 4)
    out = {"source": BASE + "/efootball/", "cutoff": str(today), "clubs": []}
    prev = {}
    if Path(a.out).exists():
        for c in json.loads(Path(a.out).read_text(encoding="utf-8"))["clubs"]:
            prev[c["squad"]] = c
    for club in clubs:
        squad = by.get(club["squad"])
        if not squad:
            print(f"no squad {club['squad']}", file=sys.stderr)
            continue
        hint = NATION.get(club.get("country", ""))
        rows = []
        for ath in squad["athletes"]:
            full, shirt, birth, nat = athlete_info(ath)
            d = match(fx, ath, hint, today)
            rows.append({"name": full, "shirt": shirt, "birth_date": birth, "nationality": nat,
                         "cbf_id": ath.get("cbf_id"), "espn_id": ath.get("espn_id"),
                         "position": ath.get("position") or ath.get("position_proposal"),
                         "goalkeeper": ath.get("goalkeeper"), "pesdb": d})
        found = sum(1 for r in rows if r["pesdb"])
        out["clubs"].append({"squad": club["squad"], "slot": club.get("slot"), "athletes": rows})
        print(f"{club['squad']:32s} {found:2d}/{len(rows)} on pesdb  (requests so far {fx.requests})", flush=True)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
