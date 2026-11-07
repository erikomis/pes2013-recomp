#!/usr/bin/env python3
"""Give the 2026 players their position, abilities, foot, height, age and nationality.

    set_player_stats_2026.py SRC DST --pesdb pesdb_2026.json --manifest manifest.json
                             --continental continental_mapping.json --squads squads.json
                             [--squads more.json] --calibrate ORIGINAL_EEDIT [--report report.json]

SRC is an EEDIT whose squads were renamed to 2026 (create_brazil_test_save.py
for the 40 Brazilian clubs, whose manifest.json maps record -> CBF athlete;
apply_continental_2026.py --mapping for the foreign clubs). pesdb_2026.json is
collect_pesdb_2026.py's output.

Player record fields (tools/pes2013_edit.py, 228 bytes), checked against
pesdb.net's PES 2013 pages for the same player IDs and against known players:

  121 & 0x0F          registered position: 0 GK 1 CWP 2 CB 3 LB 4 RB 5 DMF 6 CMF
                      7 LMF 8 RMF 9 AMF 10 LWF 11 RWF 12 SS 13 CF
  122..147 >> 1       abilities (below); bit 0 of 122 GK, 123 CWP, 124 CB, 126 DMF,
                      128 CMF, 130 AMF, 132 SS, 133 CF, 135 LB, 136 RB, 137 LMF,
                      138 RMF, 140 LWF, 142 RWF marks a position the player can play
  120 bit 7           stronger foot left
  148 bits 2..4       weak foot usage - 1;  149 bits 2..4 weak foot accuracy - 1,
  149 bits 5..7       form - 1
  216..217 >> 3 (9)   nationality (45 Brazil, 50 Argentina, 49 Uruguay ...)
  218 >> 3            age - 15
  224 bits 1..7       height - 148 cm

With a pesdb match the abilities come from the eFootball card, converted to PES
2013's list and calibrated: eFootball base cards sit about ten points below PES
2013's scale, so each ability is moved to the mean and spread (spread ratio held
to 0.7..1.6) that the Série A players of the stock Option File (--calibrate,
league 8) have, goalkeepers and outfield players apart; without one the player gets his 2026 position (or a guess from his
shirt number when the data has none; inside a broad role the shirt number
picks full back, holding or attacking midfielder, winger) and the median
abilities of matched players of that position (Série A as is, Série B 4 lower,
the foreign clubs 1 lower). Every other byte
stays as it was; the CRC is recomputed and the file decoded again.
"""
import argparse
import collections
import datetime
import json
from pathlib import Path
import statistics
import struct
import sys
import unicodedata
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes2013_edit as edit  # noqa: E402

POS = {"GK": 0, "CWP": 1, "CB": 2, "LB": 3, "RB": 4, "DMF": 5, "CMF": 6, "LMF": 7, "RMF": 8,
       "AMF": 9, "LWF": 10, "RWF": 11, "SS": 12, "CF": 13}
FLAG = {"GK": 122, "CWP": 123, "CB": 124, "DMF": 126, "CMF": 128, "AMF": 130, "SS": 132, "CF": 133,
        "LB": 135, "RB": 136, "LMF": 137, "RMF": 138, "LWF": 140, "RWF": 142}
ABILITY = {"attack": 122, "defence": 123, "balance": 124, "stamina": 125, "top_speed": 126,
           "response": 128, "explosive": 129, "dribble_acc": 130, "dribble_speed": 131,
           "short_acc": 132, "short_speed": 133, "long_acc": 134, "long_speed": 135,
           "shot_acc": 136, "kick_power": 137, "place_kick": 139, "swerve": 140, "header": 141,
           "jump": 142, "teamwork": 143, "ball_control": 144, "tenacity": 146, "gk": 147}
NATION = {"brazil": 45, "argentina": 50, "uruguay": 49, "paraguay": 48, "chile": 47, "peru": 46,
          "ecuador": 51, "colombia": 44, "bolivia": 104, "venezuela": 105, "mexico": 40,
          "portugal": 6, "spain": 7, "france": 8, "italy": 12, "germany": 14, "england": 5,
          "netherlands": 10, "belgium": 9, "united states": 39, "usa": 39, "japan": 52,
          "costa rica": 42, "honduras": 43, "panama": 89, "canada": 75, "angola": 17,
          "nigeria": 35, "ghana": 34, "cameroon": 36, "senegal": 38, "morocco": 32,
          "croatia": 24, "serbia": 14, "switzerland": 11, "poland": 19, "greece": 28,
          "turkey": 29, "russia": 31, "ukraine": 30, "australia": 57, "south korea": 53}
WF_USE = {"almost never": 1, "rarely": 2, "occasionally": 4, "regularly": 6, "often": 6, "very often": 8}
WF_ACC = {"very low": 2, "low": 3, "medium": 5, "high": 7, "very high": 8}
FORM = {"very inconsistent": 2, "inconsistent": 3, "standard": 5, "stable": 6, "unwavering": 8}
SHIRT_GUESS = {2: "RB", 3: "CB", 4: "CB", 5: "DMF", 6: "LB", 7: "RWF", 8: "CMF", 9: "CF",
               10: "AMF", 11: "LWF", 13: "CB", 14: "CB", 15: "DMF", 16: "LB", 17: "RWF",
               18: "CMF", 19: "CF", 20: "AMF", 21: "CF", 22: "RB"}
BROAD = {"Goalkeeper": "GK", "Defender": "CB", "Midfielder": "CMF", "Forward": "CF"}
# Brazilian shirt-number habits, used only inside the broad role the 2026 data gives.
BY_NUMBER = {"Defender": {2: "RB", 13: "RB", 22: "RB", 6: "LB", 16: "LB"},
             "Midfielder": {5: "DMF", 15: "DMF", 10: "AMF", 20: "AMF", 7: "RMF", 11: "LMF"},
             "Forward": {7: "RWF", 17: "RWF", 11: "LWF", 19: "SS"}}
# Template level per competition, from the median of matched players.
LEVEL = {"A": 0, "B": -4, "CONMEBOL": -1}


def key(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())


def convert(st):
    """eFootball base stats -> PES 2013 abilities (40..99)."""
    g = lambda k: st.get(k, 50)  # noqa: E731
    gk = statistics.mean([g("GK Awareness"), g("GK Catching"), g("GK Parrying"), g("GK Reflexes"), g("GK Reach")])
    is_gk = gk >= 60
    v = {
        "attack": g("Attacking Awareness"), "defence": g("Defensive Awareness"),
        "balance": g("Balance"), "stamina": g("Stamina"), "top_speed": g("Speed"),
        "response": g("GK Reflexes") if is_gk else (g("Acceleration") + max(g("Attacking Awareness"), g("Defensive Awareness"))) / 2,
        "explosive": g("Acceleration"), "dribble_acc": g("Dribbling"),
        "dribble_speed": (g("Dribbling") + g("Speed")) / 2, "short_acc": g("Low Pass"),
        "short_speed": (g("Low Pass") + g("Kicking Power")) / 2, "long_acc": g("Lofted Pass"),
        "long_speed": (g("Lofted Pass") + g("Kicking Power")) / 2, "shot_acc": g("Finishing"),
        "kick_power": g("Kicking Power"), "place_kick": g("Set Piece Taking"), "swerve": g("Curl"),
        "header": g("Heading"), "jump": g("Jumping"),
        "teamwork": (g("Low Pass") + g("Defensive Engagement") + g("Attacking Awareness")) / 3,
        "ball_control": g("Ball Control"), "tenacity": (g("Physical Contact") + g("Aggression")) / 2,
        "gk": gk if is_gk else 50,
    }
    return {k: max(40, min(99, round(x))) for k, x in v.items()}


def age_on(birth, today):
    b = datetime.date.fromisoformat(birth)
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def set_bits32(out, at, shift, width, value):
    word = int.from_bytes(out[at:at + 4], "big")
    mask = ((1 << width) - 1) << shift
    word = (word & ~mask) | ((value << shift) & mask)
    out[at:at + 4] = word.to_bytes(4, "big")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--pesdb", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--continental", required=True)
    ap.add_argument("--squads", action="append", default=[],
                    help="squad files with the 2026 data (goalkeeper, position, height, birth date)")
    ap.add_argument("--calibrate", required=True,
                    help="the stock EEDIT whose Série A players set PES 2013's ability scale")
    ap.add_argument("--positions", help="manual positions: {\"players\": {cbf_id: {\"position\": \"CMF\"}}}")
    ap.add_argument("--report")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("DST must be a different file")
    today = datetime.date(2026, 11, 4)
    data = Path(a.src).read_bytes()
    dec = edit.decode(data)
    players = {p["id"]: p for p in dec["players"]}
    pes = json.loads(Path(a.pesdb).read_text(encoding="utf-8"))
    rows = {}
    for club in pes["clubs"]:
        for r in club["athletes"]:
            if r.get("cbf_id"):
                rows[("cbf", r["cbf_id"])] = r
            rows[("club", club["squad"], key(r.get("shirt")), r.get("birth_date"))] = r
            if r.get("espn_id"):
                rows[("espn", club["squad"], r["espn_id"])] = r

    base = {}
    for f in a.squads:
        for club in json.loads(Path(f).read_text(encoding="utf-8"))["clubs"]:
            for ath in club["athletes"]:
                esp = (ath.get("espn_candidates") or [{}])[0] if ath.get("espn_candidates") else {}
                info = {"goalkeeper": ath.get("goalkeeper"),
                        "position": ath.get("position") or ath.get("position_proposal") or esp.get("position"),
                        "birth_date": ath.get("birth_date") or ath.get("birth_date_proposal") or esp.get("birth_date"),
                        "nationality": esp.get("nationality") or ath.get("nationality"),
                        "height": round(float(esp["height_inches"]) * 2.54) if esp.get("height_inches") else None}
                if ath.get("cbf_id"):
                    base[("cbf", ath["cbf_id"])] = info
                if ath.get("espn_id"):
                    base[("espn", ath["espn_id"])] = info

    override = (json.loads(Path(a.positions).read_text(encoding="utf-8"))["players"]
                if a.positions else {})
    todo = []  # (player id, group, pesdb row or None, info)
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    for ch in man["changes"]:
        group = "A" if ch.get("division_reference") == "A" else "B"
        for asg in ch["assignments"]:
            r = rows.get(("cbf", asg["cbf_id"]))
            info = dict(base.get(("cbf", asg["cbf_id"]), {}))
            info["cbf_id"] = asg["cbf_id"]
            info["shirt_number"] = asg.get("shirt_number")
            todo.append((asg["pes_id"], group, r, info))
    for m in json.loads(Path(a.continental).read_text(encoding="utf-8")):
        ath = m["athlete"]
        r = rows.get(("espn", m["squad"], ath.get("espn_id"))) or \
            rows.get(("club", m["squad"], key(ath.get("display_name")), ath.get("birth_date")))
        info = dict(base.get(("espn", ath.get("espn_id")), {}))
        info.update({k: v for k, v in (("shirt_number", ath.get("shirt_number")),
                                         ("position", ath.get("position")),
                                         ("birth_date", ath.get("birth_date"))) if v})
        todo.append((m["player_id"], "CONMEBOL", r, info))

    # Calibration: eFootball -> PES 2013 scale, per ability, goalkeepers and outfield apart.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import set_leagues  # noqa: E402
    od = Path(a.calibrate).read_bytes()
    odec = edit.decode(od)
    oplayers = {p["id"]: p for p in odec["players"]}
    orosters = {r["team_id"]: r for r in odec["rosters"]}
    ref = {"GK": [], "OUT": []}
    for tid in set_leagues.read_leagues(od, set_leagues.ORIGINAL)[8]:
        for mm in orosters[tid]["members"]:
            o = oplayers[mm["player_id"]]["offset"]
            ref["GK" if od[o + 121] & 15 == 0 else "OUT"].append({k: od[o + at] >> 1 for k, at in ABILITY.items()})
    raw = {"GK": [], "OUT": []}
    for pid, group, r, info in todo:
        d = (r or {}).get("pesdb")
        if d and d.get("primary") in POS:
            raw["GK" if d["primary"] == "GK" else "OUT"].append(convert(d["stats"]))
    cal = {}
    for g in ("GK", "OUT"):
        for k in ABILITY:
            rv = [x[k] for x in ref[g]]
            ev = [x[k] for x in raw[g]] or rv
            rm, em = statistics.mean(rv), statistics.mean(ev)
            rs, es = statistics.pstdev(rv), statistics.pstdev(ev)
            ratio = min(1.6, max(0.7, rs / es)) if es > 1 and len(ev) >= 20 else 1.0
            cal[(g, k)] = (em, rm, ratio)

    def calibrate(ab, gk):
        g = "GK" if gk else "OUT"
        out = {}
        for k, v in ab.items():
            em, rm, ratio = cal[(g, k)]
            out[k] = max(40, min(99, round(rm + (v - em) * ratio)))
        if not gk:
            out["gk"] = 50
        return out

    # Templates: median calibrated abilities per (group, position) of matched players.
    pool = collections.defaultdict(list)
    for pid, group, r, info in todo:
        if r and r.get("pesdb") and r["pesdb"].get("primary") in POS:
            c = calibrate(convert(r["pesdb"]["stats"]), r["pesdb"]["primary"] == "GK")
            pool[(group, r["pesdb"]["primary"])].append(c)
            pool[("ALL", r["pesdb"]["primary"])].append(c)

    def template(group, pos):
        rows_ = pool.get((group, pos)) or pool.get(("ALL", pos)) or pool.get(("ALL", "CMF"))
        t = {k: max(40, round(statistics.median(x[k] for x in rows_)) + LEVEL.get(group, -2)) for k in ABILITY}
        if pos != "GK":
            t["gk"] = 50
        return t

    out = bytearray(data)
    allowed = bytearray(len(data))
    allowed[8:12] = b"\1" * 4
    counts = collections.Counter()
    report = []
    seen = set()
    for pid, group, r, info in todo:
        if pid in seen or pid not in players:
            continue
        seen.add(pid)
        o = players[pid]["offset"]
        d = (r or {}).get("pesdb")
        if d and d.get("primary") in POS:
            pos = d["primary"]
            playable = {pos} | {p for p in d.get("secondary", []) if p in POS}
            ab = calibrate(convert(d["stats"]), pos == "GK")
            source = "pesdb"
        else:
            broad = (r or {}).get("position") or info.get("position")
            manual = override.get(info.get("cbf_id"), {}).get("position")
            if manual in POS:
                pos = manual
            elif (r or {}).get("goalkeeper") or info.get("goalkeeper") or broad == "Goalkeeper":
                pos = "GK"
            elif broad in BROAD:
                try:
                    num = int(info.get("shirt_number") or 0)
                except (TypeError, ValueError):
                    num = 0
                pos = BY_NUMBER.get(broad, {}).get(num, BROAD[broad])
            else:
                try:
                    pos = SHIRT_GUESS.get(int(info.get("shirt_number") or 0), "CMF")
                except (TypeError, ValueError):
                    pos = "CMF"
            playable = {pos}
            ab = template(group, pos)
            source = "template"
        counts[source] += 1
        rec = out[o:o + 228]
        rec[121] = (rec[121] & 0xF0) | POS[pos]
        for name, at in ABILITY.items():
            rec[at] = (ab[name] << 1) | (rec[at] & 1)
        for p, at in FLAG.items():
            rec[at] = (rec[at] & 0xFE) | (1 if p in playable else 0)
        if d:
            if d.get("foot"):
                rec[120] = (rec[120] & 0x7F) | (0x80 if "left" in d["foot"].lower() else 0)
            wu = WF_USE.get((d.get("weak_foot_usage") or "").lower())
            wa = WF_ACC.get((d.get("weak_foot_accuracy") or "").lower())
            fm = FORM.get((d.get("form") or "").lower())
            if wu:
                rec[148] = (rec[148] & ~0x1C) | ((wu - 1) << 2)
            if wa:
                rec[149] = (rec[149] & ~0x1C) | ((wa - 1) << 2)
            if fm:
                rec[149] = (rec[149] & ~0xE0) | ((fm - 1) << 5)
        height = (d or {}).get("height") or info.get("height")
        if height and 148 <= height <= 148 + 127:
            rec[224] = (rec[224] & 0x01) | ((height - 148) << 1)
        birth = (r or {}).get("birth_date") or info.get("birth_date")
        age = age_on(birth, today) if birth else (d or {}).get("age")
        if age:
            rec[218] = (rec[218] & 0x07) | ((max(15, min(46, age)) - 15) << 3)
        nat = NATION.get(key((d or {}).get("nationality") or (r or {}).get("nationality") or info.get("nationality")))
        if nat:
            set_bits32(rec, 214, 3, 9, nat)
        out[o:o + 228] = rec
        for at in [120, 121, 148, 149, 214, 215, 216, 217, 218, 224] + list(range(122, 148)):
            allowed[o + at] = 1
        report.append({"player_id": pid, "name": players[pid]["name"], "group": group,
                       "position": pos, "playable": sorted(playable), "source": source,
                       "pesdb": (d or {}).get("path"), "abilities": ab, "height": height, "age": age})

    struct.pack_into(">I", out, 8, edit.crc32(out))
    if any(x != y and not allowed[i] for i, (x, y) in enumerate(zip(data, out))):
        raise SystemExit("a byte outside the player fields changed")
    after = edit.decode(bytes(out))
    if [(p["id"], p["name"]) for p in after["players"]] != [(p["id"], p["name"]) for p in dec["players"]]:
        raise SystemExit("players changed")
    Path(a.dst).write_bytes(out)
    if a.report:
        Path(a.report).write_text(json.dumps({"counts": counts, "players": report},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(report)} players: {counts['pesdb']} from pesdb, {counts['template']} from the "
          f"position template -> {a.dst}")


if __name__ == "__main__":
    main()
