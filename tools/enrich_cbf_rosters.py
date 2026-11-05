#!/usr/bin/env python3
"""Fetch public athlete profiles and prepare a reviewable, unapplied 32-slot draft."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from collect_cbf_rosters import BASE


def profile_from_html(html):
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', html):
        fragment = json.loads(match[1])
        text = fragment[1] if len(fragment) > 1 and isinstance(fragment[1], str) else ""
        marker = '"data":'
        start = text.find(marker)
        if start < 0:
            continue
        value, _ = json.JSONDecoder().raw_decode(text[start + len(marker):].lstrip())
        if isinstance(value, dict) and "atleta_data_nascimento" in value:
            # Exclude embedded photos and unrelated history to keep evidence small.
            return {key: value[key] for key in ("atleta_id", "atleta_nome", "atleta_apelido",
                    "atleta_data_nascimento", "atleta_time_atual", "atleta_estatisticas", "jogos")}
    raise ValueError("Athlete profile payload not found")


def fetch_profile(division, athlete_id, year, cache, offline=False):
    path = cache / f"{division}-{athlete_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    if offline:
        raise FileNotFoundError("Profile not cached; offline mode")
    url = f"{BASE}/futebol-brasileiro/atletas/campeonato-brasileiro/serie-{division.lower()}/{year}/{athlete_id}"
    time.sleep(2)
    with urlopen(Request(url, headers={"User-Agent": "PES-roster-research/1.0"}), timeout=25) as response:
        data = response.read()
    result = profile_from_html(data.decode("utf-8"))
    if str(result["atleta_id"]) != athlete_id:
        raise ValueError("Profile returned a different athlete")
    result["source_url"] = url
    result["source_sha256"] = hashlib.sha256(data).hexdigest()
    result["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def appearances(profile, club_id, cutoff):
    dates = []
    for divisions in (profile.get("jogos") or {}).values():
        for matches in divisions.values():
            for match in matches:
                if club_id not in (str(match.get("codigo_time_mandante")), str(match.get("codigo_time_visitante"))):
                    continue
                try:
                    played = datetime.strptime(match["data"].strip(), "%d/%m/%Y").date()
                except (ValueError, KeyError):
                    continue
                if match.get("encerrado") and played <= cutoff:
                    dates.append(played)
    return sorted(set(dates), reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registrations", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="Use only cached profiles; no requests")
    args = parser.parse_args()
    data = json.loads(args.registrations.read_text())
    cutoff = date.fromisoformat(data["requested_cutoff"])
    args.cache.mkdir(parents=True, exist_ok=True)
    queries = {(club["division"], athlete["cbf_id"]) for club in data["clubs"]
               for athlete in club["athletes"] if athlete["status"] != "different_current_club"}
    profiles, errors = {}, []
    failures = 0
    stopped = False
    for count, key in enumerate(sorted(queries), 1):
        try:
            profiles[key] = fetch_profile(*key, data["season"], args.cache,
                                          offline=args.offline or stopped)
            failures = 0
        except Exception as exc:
            errors.append(dict(division=key[0], cbf_id=key[1], error=str(exc)))
            failures += 1
            if not args.offline and not stopped:
                print(f"Profile {key}: {exc}", flush=True)
                if failures >= 3:
                    stopped = True
                    print("Three consecutive failures; stopping network requests, preserving cached evidence.", flush=True)
        if count % 100 == 0 or count == len(queries):
            print(f"Profiles {count}/{len(queries)}; missing/errors {len(errors)}", flush=True)
    for club in data["clubs"]:
        candidates = []
        for athlete in club["athletes"]:
            profile = profiles.get((club["division"], athlete["cbf_id"]))
            if profile is None:
                continue
            athlete["profile_url"] = profile["source_url"]
            athlete["birth_date_source"] = profile["atleta_data_nascimento"]
            try:
                athlete["birth_date"] = datetime.strptime(profile["atleta_data_nascimento"], "%d/%m/%Y").date().isoformat()
            except (ValueError, TypeError):
                pass
            current = profile.get("atleta_time_atual") or {}
            athlete["profile_current_club_id"] = str(current.get("time_id", ""))
            if athlete["profile_current_club_id"] != club["cbf_id"]:
                athlete["review_status"] = "profile_current_club_differs"
                continue
            dates = appearances(profile, club["cbf_id"], cutoff)
            athlete["match_dates"] = [day.isoformat() for day in dates]
            athlete["recent_match_count"] = sum(day >= cutoff - timedelta(days=90) for day in dates)
            athlete["season_match_count"] = len(dates)
            athlete["review_status"] = "profile_confirms_club_position_and_number_pending"
            candidates.append(athlete)
        # Deduplicate repeated CBF registration rows by stable athlete identity.
        candidates = list({a["cbf_id"]: a for a in candidates}.values())
        candidates.sort(key=lambda a: (-a["recent_match_count"], -a["season_match_count"], a["full_name"]))
        club["draft_squad_ids"] = [a["cbf_id"] for a in candidates[:32]]
        club["draft_overflow_ids"] = [a["cbf_id"] for a in candidates[32:]]
        club["draft_needs_review"] = True
        club["profile_coverage_complete"] = all(
            (club["division"], a["cbf_id"]) in profiles for a in club["athletes"]
            if a["status"] != "different_current_club")
        if not club["profile_coverage_complete"]:
            # Partial retrieval must not silently favor the first cached IDs.
            club["draft_squad_ids"] = []
            club["draft_overflow_ids"] = []
    data["profile_errors"] = errors
    data["profile_count"] = len(profiles)
    data["network_stopped_after_failures"] = stopped
    data["status"] = "draft_32_requires_positions_numbers_and_professional_squad_review"
    data["selection_policy"] = "Up to 32 per club: current-club profile ID, recent 90-day match listings, then season match listings. No playing time inferred; bench listings may occur. Injured players, backup goalkeepers and new signings require review."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
