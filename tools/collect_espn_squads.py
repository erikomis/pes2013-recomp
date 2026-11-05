#!/usr/bin/env python3
"""Collect complementary 2026 squad positions; CBF remains the club list authority."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

from collect_cbf_rosters import normalize_club


def club_key(club):
    name = normalize_club(club["name"])
    if name == "botafogo" and club["name"].rsplit("-", 1)[-1].strip() == "SP":
        return "botafogo sp"
    return {"athletico paranaense": "athletico pr", "atletico mineiro": "atletico mg",
            "america": "america mineiro", "santos fc": "santos", "operario": "operario pr",
            "gremio novorizontino": "novorizontino", "sport recife": "sport"}.get(name, name)


def get_json(url, path, offline):
    if path.exists():
        return json.loads(path.read_text())
    if offline:
        raise ValueError("Not cached; offline mode")
    time.sleep(2)
    with urlopen(url, timeout=20) as response:
        data = response.read()
    result = json.loads(data)
    path.write_bytes(data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registrations", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    registrations = json.loads(args.registrations.read_text())
    lists = {}
    for div, league in (("A", "bra.1"), ("B", "bra.2")):
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams?limit=100&season=2026"
        data = get_json(url, args.cache / f"serie-{div.lower()}.json", args.offline)
        lists[div] = [item["team"] for item in data["sports"][0]["leagues"][0]["teams"]]
    clubs, errors = [], []
    failures = 0
    stopped = False
    for club in registrations["clubs"]:
        try:
            matches = [t for t in lists[club["division"]] if normalize_club(t["displayName"]) == club_key(club)]
            if len(matches) != 1:
                raise ValueError("No unique ESPN club identity")
            team = matches[0]
            league = "bra.1" if club["division"] == "A" else "bra.2"
            url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team["id"]}/roster?season=2026'
            data = get_json(url, args.cache / f'{team["id"]}-roster.json', args.offline or stopped)
            if data.get("season", {}).get("year") != 2026 or str(data.get("team", {}).get("id")) != str(team["id"]):
                raise ValueError("Wrong roster season or team")
            athletes = []
            for a in data["athletes"]:
                athletes.append(dict(espn_id=str(a["id"]), full_name=a["fullName"],
                    display_name=a["displayName"], shirt_number=a.get("jersey"),
                    position=a.get("position", {}).get("name"), position_code=a.get("position", {}).get("abbreviation"),
                    birth_date=(a.get("dateOfBirth") or "")[:10] or None,
                    nationality=a.get("citizenship"), height_inches=a.get("height"),
                    weight_pounds=a.get("weight"), status=a.get("status", {}).get("name")))
            if not athletes:
                raise ValueError("Empty roster")
            clubs.append(dict(cbf_id=club["cbf_id"], name=club["name"], division=club["division"],
                espn_team_id=str(team["id"]), source_url=url, source_timestamp=data.get("timestamp"),
                source_sha256=hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(), athletes=athletes))
            failures = 0
            print(f'{club["name"]}: {len(athletes)}', flush=True)
        except Exception as exc:
            errors.append(dict(cbf_id=club["cbf_id"], error=str(exc)))
            failures += 1
            if failures >= 3:
                stopped = True
            print(f'{club["name"]}: {exc}', flush=True)
    args.output.write_text(json.dumps(dict(season=2026, requested_cutoff=registrations["requested_cutoff"],
        collected_at_utc=datetime.now(timezone.utc).isoformat(), status="complementary_reference_requires_identity_crosscheck",
        installed=False, clubs=clubs, errors=errors), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
