#!/usr/bin/env python3
"""Collect public CBF A/B registration evidence, never write a game save.

The CBF competition list includes former players and youth registrations.
Candidates must be reviewed before becoming a playable squad.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen

BASE = "https://www.cbf.com.br"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.label).strip()))
            self.href = None


def normalize_club(name):
    name = re.sub(r"\s+-\s+[A-Z]{2}$", "", name)
    name = unicodedata.normalize("NFKD", name.casefold())
    name = "".join(c for c in name if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", name)
    return " ".join(w for w in words if w != "saf")


def clubs_from_html(html, division, year):
    parser = Links()
    parser.feed(html)
    pattern = re.compile(rf"^/futebol-brasileiro/times/campeonato-brasileiro/serie-{division}/{year}/(\d+)$")
    clubs = {}
    for href, label in parser.links:
        match = pattern.fullmatch(href.removeprefix(BASE))
        if match and label:
            clubs[match[1]] = dict(cbf_id=match[1], name=label,
                                  division=division.upper(), source_url=BASE + href.removeprefix(BASE))
    if len(clubs) != 20:
        raise ValueError(f"Expected 20 clubs in division {division}, got {len(clubs)}")
    return list(clubs.values())


def athletes_from_html(html):
    # Next.js embeds the same public table, with stable athlete identifiers.
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', html):
        fragment = json.loads(match[1])
        if len(fragment) < 2 or not isinstance(fragment[1], str):
            continue
        text = fragment[1]
        marker = '"atletas":'
        start = text.find(marker)
        if start < 0:
            continue
        records, _ = json.JSONDecoder().raw_decode(text[start + len(marker):].lstrip())
        if not isinstance(records, list) or not records:
            raise ValueError("CBF returned an empty athlete list")
        required = {"atleta_id", "atleta_nome", "Atleta_apelido", "clube_nome_popular"}
        if any(not required <= record.keys() for record in records):
            raise ValueError("CBF athlete schema changed")
        return records
    raise ValueError("No public athlete payload found in CBF HTML")


def fetch(url, path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    req = Request(url, headers={"User-Agent": "PES-roster-research/1.0"})
    with urlopen(req, timeout=30) as response:
        data = response.read()
    html = data.decode("utf-8")
    path.write_bytes(data)
    return html


def collect(year, cutoff, cache):
    clubs = []
    for division in ("a", "b"):
        url = f"{BASE}/futebol-brasileiro/times/campeonato-brasileiro/serie-{division}/{year}"
        clubs.extend(clubs_from_html(fetch(url, cache / f"serie-{division}.html"), division, year))
    all_records = defaultdict(list)
    for club in clubs:
        html = fetch(club["source_url"], cache / f'{club["cbf_id"]}.html')
        club["source_sha256"] = hashlib.sha256(html.encode()).hexdigest()
        club["athletes"] = []
        for raw in athletes_from_html(html):
            same_state = raw.get("clube_uf") == club["name"].rsplit("-", 1)[-1].strip()
            record = dict(cbf_id=str(raw["atleta_id"]), full_name=raw["atleta_nome"],
                          display_name=raw["Atleta_apelido"], current_club=raw["clube_nome_popular"],
                          current_club_state=raw.get("clube_uf"),
                          status="candidate" if same_state and normalize_club(raw["clube_nome_popular"]) == normalize_club(club["name"]) else "different_current_club",
                          position=None, shirt_number=None, birth_date=None)
            club["athletes"].append(record)
            all_records[record["cbf_id"]].append((club["cbf_id"], record))
        print(f'{club["division"]} {club["name"]}: {len(club["athletes"])} registrations', flush=True)
    conflicts = []
    for athlete_id, entries in all_records.items():
        current_clubs = {normalize_club(record["current_club"]) + "/" + str(record["current_club_state"]) for _, record in entries}
        candidates = [record for _, record in entries if record["status"] == "candidate"]
        if len(current_clubs) > 1 or len(candidates) > 1:
            conflicts.append(dict(cbf_id=athlete_id, clubs=sorted(current_clubs)))
            for _, record in entries:
                record["status"] = "conflicting_registration"
    return dict(season=year, requested_cutoff=cutoff,
                collected_at_utc=datetime.now(timezone.utc).isoformat(),
                status="registration_evidence_requires_review", game_save_modified=False,
                caveat="Live pages are not a historical cutoff guarantee. Includes youth and former players. Candidate does not mean final first-team selection. CBF clube_id on an athlete row can repeat the queried club despite a different current club; classification uses the club name.",
                clubs=clubs, conflicts=conflicts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--cutoff", default="2026-11-04")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # A separate dated cache preserves the evidence used for each snapshot.
    args.cache.mkdir(parents=True, exist_ok=True)
    result = collect(args.year, args.cutoff, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
