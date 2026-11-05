#!/usr/bin/env python3
"""Collect recent CBF match lists as professional-squad evidence, not a game patch."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.request import urlopen


def payload(html, key):
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', html):
        fragment = json.loads(match[1])
        text = fragment[1] if len(fragment) > 1 and isinstance(fragment[1], str) else ""
        for marker in re.finditer('"data":', text):
            value, _ = json.JSONDecoder().raw_decode(text[marker.end():].lstrip())
            if isinstance(value, dict) and key in value:
                return value
    raise ValueError(f"Missing CBF payload: {key}")


def slug(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub("[^a-z0-9]+", "-", name).strip("-")


def match_evidence(raw, url, played, expected_id):
    game = payload(raw, "jogo")["jogo"]
    if str(game["id_jogo"]) != expected_id:
        raise ValueError("Wrong match returned")
    teams = []
    for side in ("mandante", "visitante"):
        team = game[side]
        athletes = []
        for a in team.get("atletas", []):
            athletes.append(dict(cbf_id=str(a["id"]),
                name=re.sub(r"^\d+\s*-\s*", "", a["nome"]),
                display_name=re.sub(r"^\d+\s*-\s*", "", a["apelido"]),
                shirt_number=int(a["numero_camisa"]),
                goalkeeper=str(a["goleiro"]).lower() == "true",
                started=str(a["entrou_jogando"]).lower() == "true"))
        if not athletes:
            raise ValueError("Match lacks an athlete list")
        teams.append(dict(cbf_id=str(team["id"]), name=team["nome"], athletes=athletes))
    return dict(match_id=expected_id, date=played, source_url=url, teams=teams,
                source_sha256=hashlib.sha256(raw.encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registrations", type=Path)
    parser.add_argument("--club-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matches", type=int, default=3)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.matches <= 5:
        parser.error("--matches must be between 1 and 5")
    registrations = json.loads(args.registrations.read_text())
    cutoff = date.fromisoformat(registrations["requested_cutoff"])
    cache = args.club_cache / "matches"
    cache.mkdir(exist_ok=True)
    wanted = {}
    club_games = {}
    for club in registrations["clubs"]:
        source = payload((args.club_cache / f'{club["cbf_id"]}.html').read_text(), "jogos")
        games = []
        for game in source["jogos"]:
            played = datetime.strptime(game["data"].strip(), "%d/%m/%Y").date()
            if played <= cutoff:
                games.append((played, game))
        games.sort(key=lambda item: item[0], reverse=True)
        club_games[club["cbf_id"]] = [str(g["id_jogo"]) for _, g in games[:args.matches]]
        for played, game in games[:args.matches]:
            match_id = str(game["id_jogo"])
            names = slug(game["mandante"]["nome"]) + "-x-" + slug(game["visitante"]["nome"])
            url = f'https://www.cbf.com.br/futebol-brasileiro/jogos/campeonato-brasileiro/serie-{club["division"].lower()}/2026/{names}/{match_id}?view=escalacao'
            wanted[match_id] = (played.isoformat(), url)
    matches, errors = {}, []
    failures = 0
    stopped = False
    for index, (match_id, (played, url)) in enumerate(sorted(wanted.items()), 1):
        path = cache / f"{match_id}.json"
        try:
            if path.exists():
                match = json.loads(path.read_text())
            else:
                if args.offline or stopped:
                    raise ValueError("Not cached; network disabled")
                time.sleep(2)
                with urlopen(url, timeout=20) as response:
                    raw = response.read().decode()
                match = match_evidence(raw, url, played, match_id)
                path.write_text(json.dumps(match, ensure_ascii=False, indent=2) + "\n")
            matches[match_id] = match
            failures = 0
        except Exception as exc:
            failures += 1
            errors.append(dict(match_id=match_id, source_url=url, error=str(exc)))
            if failures >= 3:
                stopped = True
        print(f"Matches {index}/{len(wanted)}; errors {len(errors)}", flush=True)
    clubs = []
    for club in registrations["clubs"]:
        ids = club_games[club["cbf_id"]]
        current = {a["cbf_id"] for a in club["athletes"] if a["status"] == "candidate"}
        players = {}
        for match_id in ids:
            match = matches.get(match_id)
            if not match:
                continue
            for team in match["teams"]:
                if team["cbf_id"] != club["cbf_id"]:
                    continue
                for athlete in team["athletes"]:
                    a = players.setdefault(athlete["cbf_id"], dict(**athlete, evidence=[],
                        current_registration_confirmed=athlete["cbf_id"] in current))
                    a["evidence"].append(dict(date=match["date"], source_url=match["source_url"],
                        shirt_number=athlete["shirt_number"], started=athlete["started"]))
        athletes = sorted(players.values(), key=lambda a: (-len(a["evidence"]), -sum(e["started"] for e in a["evidence"]), a["name"]))
        complete = len(ids) == args.matches and all(i in matches for i in ids)
        selected = [a["cbf_id"] for a in athletes if a["current_registration_confirmed"]][:32] if complete else []
        clubs.append(dict(cbf_id=club["cbf_id"], name=club["name"], division=club["division"],
            coverage_complete=complete, match_ids=ids, athletes=athletes, draft_squad_ids=selected))
    args.output.write_text(json.dumps(dict(status="recent_match_evidence_requires_position_and_identity_review",
        cutoff=cutoff.isoformat(), match_count=len(matches), errors=errors, clubs=clubs,
        installed=False, caveat="Match listings include substitutes. Injured players and new signings may be absent; verify against official professional squads. Outfield positions are unknown."), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
