#!/usr/bin/env python3
"""Join recent CBF squads to ESPN evidence, keeping identity ambiguity explicit."""
import argparse
import csv
import json
from pathlib import Path
import re
import unicodedata


def name_key(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in value if not unicodedata.combining(c))))


def identity_candidates(athlete, references):
    names = {name_key(athlete["name"]), name_key(athlete["display_name"])} - {""}
    exact = [r for r in references if names & {name_key(r["full_name"]), name_key(r["display_name"])}]
    if exact:
        return "exact_name_requires_identity_review", exact
    # Multi-word subset is a suggestion, not an accepted player ID assignment.
    full = set(name_key(athlete["name"]).split())
    candidates = []
    for reference in references:
        other = set(name_key(reference["full_name"]).split())
        if len(other) >= 2 and len(full) >= 2 and (other <= full or full <= other):
            candidates.append(reference)
    return "name_subset_requires_identity_review", candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recent", type=Path)
    parser.add_argument("positions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.recent.read_text())
    references = {c["cbf_id"]: c for c in json.loads(args.positions.read_text())["clubs"]}
    resolved = selected = 0
    for club in data["clubs"]:
        provider = references.get(club["cbf_id"], {})
        for athlete in club["athletes"]:
            selected += athlete["cbf_id"] in club["draft_squad_ids"]
            status, candidates = identity_candidates(athlete, provider.get("athletes", []))
            athlete["identity_match_status"] = status if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
            athlete["espn_candidates"] = candidates
            athlete["position_source"] = provider.get("source_url")
            athlete["identity_reviewed"] = False
            athlete["pes_player_id"] = None
            athlete["attributes_verified"] = False
            if len(candidates) == 1:
                reference = candidates[0]
                athlete["position_proposal"] = reference["position"]
                athlete["birth_date_proposal"] = reference["birth_date"]
                athlete["goalkeeper_disagreement"] = athlete["goalkeeper"] != (reference["position_code"] == "G")
                athlete["shirt_number_disagreement"] = str(athlete["shirt_number"]) != str(reference["shirt_number"])
                resolved += athlete["cbf_id"] in club["draft_squad_ids"]
    data["status"] = "draft_with_position_proposals_not_installable"
    data["summary"] = dict(selected_candidates=selected, unique_position_proposals=resolved,
                            unresolved_selected_candidates=selected-resolved)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    with args.csv.open("w", encoding="utf-8", newline="") as stream:
        columns = ["division", "club", "cbf_id", "name", "shirt_number", "goalkeeper", "position_proposal",
                   "birth_date_proposal", "identity_match_status", "shirt_number_disagreement", "goalkeeper_disagreement",
                   "latest_match_date", "match_source", "position_source"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for club in data["clubs"]:
            for a in club["athletes"]:
                if a["cbf_id"] not in club["draft_squad_ids"]:
                    continue
                row = {key: a.get(key) for key in columns}
                row.update(division=club["division"], club=club["name"],
                           latest_match_date=a["evidence"][0]["date"], match_source=a["evidence"][0]["source_url"])
                writer.writerow(row)
    print(json.dumps(data["summary"]))


if __name__ == "__main__":
    main()
