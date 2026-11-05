#!/usr/bin/env python3
"""Join CBF evidence to observed local team names; never guess replacement slots."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from collect_cbf_rosters import normalize_club

# Historical spellings, used only for an explicit-name match. Unknown clubs
# remain unmapped; continental duplicates are not substituted for domestic teams.
ALIASES = {
    "athletico paranaense": "ATLÉTICO PR",
    "america": "AMÉRICA MG",
    "atletico goianiense": "ATLÉTICO GOIANIENSE",
    "bahia": "EC BAHIA",
    "botafogo": "BOTAFOGO",
    "corinthians": "SC CORINTHIANS",
    "flamengo": "CR FLAMENGO",
    "fluminense": "FLUMINENSE FC",
    "internacional": "SC INTERNACIONAL",
    "red bull bragantino": "BRAGANTINO",
    "vasco da gama": "VASCO DA GAMA",
}


def match_team(club, teams):
    name = normalize_club(club["name"])
    if name == "botafogo" and club["name"].rsplit("-", 1)[-1].strip() != "RJ":
        return []
    target = normalize_club(ALIASES.get(name, name))
    return [team for team in teams if team["id"] < 0x4000 and team["roster"] is not None
            and normalize_club(team["name"]) == target]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registrations", type=Path)
    parser.add_argument("existing", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.registrations.read_text())
    existing = json.loads(args.existing.read_text())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    mappings = []
    with (args.out_dir / "athletes.csv").open("w", encoding="utf-8", newline="") as stream:
        columns = ["division", "club", "cbf_club_id", "cbf_athlete_id", "full_name", "display_name",
                   "current_club", "current_club_state", "status", "birth_date", "source_url", "profile_url"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for club in data["clubs"]:
            matches = match_team(club, existing["teams"])
            mappings.append(dict(cbf_id=club["cbf_id"], name=club["name"], division=club["division"],
                                 status="name_match_requires_league_review" if len(matches) == 1 else "slot_required_or_ambiguous",
                                 pes_team_id=matches[0]["id"] if len(matches) == 1 else None))
            for athlete in club["athletes"]:
                writer.writerow(dict(division=club["division"], club=club["name"], cbf_club_id=club["cbf_id"],
                    cbf_athlete_id=athlete["cbf_id"], full_name=athlete["full_name"], display_name=athlete["display_name"],
                    current_club=athlete["current_club"], current_club_state=athlete.get("current_club_state"),
                    status=athlete.get("review_status", athlete["status"]), birth_date=athlete.get("birth_date"),
                    source_url=club["source_url"], profile_url=athlete.get("profile_url")))
    (args.out_dir / "team_mapping.json").write_text(json.dumps(mappings, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Brasil 2026 — revisão dos dados", "", "**Preparação; não instalado no jogo.**",
             "", "Recorte: " + data["requested_cutoff"] + ". Até 32 jogadores do profissional por clube.",
             "", "Os números abaixo são registros da CBF, incluindo base e ex-atletas; não são elencos finais.",
             "", "| Série | Clube | Registros | Candidatos sem conflito | Slot no PES |",
             "|---|---|---:|---:|---|"]
    for club, mapping in zip(data["clubs"], mappings):
        counts = Counter(a["status"] for a in club["athletes"])
        slot = f'0x{mapping["pes_team_id"]:04X} (nome encontrado)' if mapping["pes_team_id"] is not None else "A definir"
        lines.append(f'| {club["division"]} | {club["name"]} | {len(club["athletes"])} | {counts["candidate"]} | {slot} |')
    lines += ["", f'Fichas individuais coletadas: {data.get("profile_count", 0)}.',
              f'Identidades com registros conflitantes: {len(data["conflicts"])}.',
              "", "Pendências: posições, números de camisa 2026, revisão dos 32 profissionais,",
              "identidade CBF↔PES, atributos, slots e estrutura das ligas, gravação e teste no jogo.",
              "", "`athletes.csv` contém as fontes de cada registro; `team_mapping.json` contém os vínculos propostos.",
              "Números de camisa do save são de sua base antiga e não foram tratados como números de 2026."]
    (args.out_dir / "REVIEW.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(dict(clubs=len(mappings), matched=sum(m["pes_team_id"] is not None for m in mappings),
                          registrations=sum(len(c["athletes"]) for c in data["clubs"]))))


if __name__ == "__main__":
    main()
