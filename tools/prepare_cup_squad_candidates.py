#!/usr/bin/env python3
"""Combine dated appearances and matching current CBF club labels into draft squads."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from collect_cbf_rosters import athletes_from_html, normalize_club
from collect_recent_squads import payload


def main():
    root = Path('analysis/competitions-2026')
    mappings = json.loads((root / 'cbf_identity_map.json').read_text())
    identities = {c['key']: c for c in json.loads((root / 'participants.json').read_text())['clubs']}
    lineups = {c['club_key']: c for c in json.loads((root / 'domestic_lineup_evidence.json').read_text())['clubs']}
    clubs = []
    for mapping in mappings:
        if mapping['reused_AB']:
            continue
        club = identities[mapping['club_key']]
        paths = [root / f"cbf-clubs/{mapping['cbf_id']}.html"]
        paths.extend(sorted((root / 'domestic-lineups').glob(f"club-{mapping['cbf_id']}-*.html")))
        pages = []
        names = {normalize_club(club['name']), normalize_club(mapping['name'])}
        for path in paths:
            page = payload(path.read_text(), 'jogos')
            if str(page['campeonato']['exercicio']) != '2026' or not any(str(t['time_id']) == mapping['cbf_id'] for t in page['time']):
                raise ValueError(f'Wrong CBF identity in {path}')
            names.update(normalize_club(t['time_nome']) for t in page['time'] if str(t['time_id']) == mapping['cbf_id'])
            pages.append((path, athletes_from_html(path.read_text())))
        records = defaultdict(list)
        for path, rows in pages:
            for a in rows:
                records[str(a['atleta_id'])].append(dict(name=a['atleta_nome'], display_name=a['Atleta_apelido'],
                    current_club=a['clube_nome_popular'], state=a.get('clube_uf'), source_path=str(path),
                    club_label_matches=normalize_club(a['clube_nome_popular']) in names and a.get('clube_uf') == club['state']))
        current = {pid for pid, rows in records.items() if all(a['club_label_matches'] for a in rows)}
        conflicting = [pid for pid, rows in records.items() if any(a['club_label_matches'] for a in rows)
                       and not all(a['club_label_matches'] for a in rows)]
        evidence = lineups[mapping['club_key']]
        players = {}
        for match in evidence['matches']:
            for started, group in ((True, 'starters'), (False, 'substitutes')):
                for a in match[group]:
                    entry = players.setdefault(a['cbf_id'], dict(**a, evidence=[], position='GK' if a['goalkeeper'] else None,
                        current_club_label_matches=a['cbf_id'] in current, identity_verified=False,
                        pes_player_id=None, face_id=None))
                    entry['evidence'].append(dict(date=match['date'], match_id=match['match_id'],
                        source_url=match['source_url'], started=started, shirt_number=a['shirt_number']))
        ranked = sorted(players.values(), key=lambda a: (max(e['date'] for e in a['evidence']),
                        len(a['evidence']), sum(e['started'] for e in a['evidence'])), reverse=True)
        eligible = [a for a in ranked if a['current_club_label_matches']]
        keepers = [a for a in eligible if a['goalkeeper']][:3]
        selected = keepers + [a for a in eligible if a not in keepers][:32-len(keepers)]
        assert len(selected) <= 32 and len({a['cbf_id'] for a in selected}) == len(selected)
        latest = evidence['matches'][0] if evidence['matches'] else None
        starting_ids = [a['cbf_id'] for a in latest['starters']] if latest else []
        selection_ids = {a['cbf_id'] for a in selected}
        flags = ['outfield_positions_and_PES_identities_pending', 'injuries_and_new_signings_need_review']
        if len(evidence['matches']) < 3:
            flags.append('fewer_than_three_match_references')
        if len(selected) < 18:
            flags.append('fewer_than_18_candidates')
        if len(keepers) < 2:
            flags.append('fewer_than_two_goalkeepers')
        if evidence['age_days'] is None or evidence['age_days'] > 30:
            flags.append('latest_available_match_over_30_days_or_missing')
        if not (len(starting_ids) == 11 and set(starting_ids) <= selection_ids):
            flags.append('latest_starting_eleven_not_fully_in_candidate_squad')
        if conflicting:
            flags.append('conflicting_current_club_labels_excluded')
        clubs.append(dict(club_key=club['key'], cbf_id=mapping['cbf_id'], name=club['name'], state=club['state'],
            status='draft_requires_review_not_installable', latest_match_date=evidence['latest_match_date'],
            latest_match_age_days=evidence['age_days'], athletes=ranked,
            draft_squad_ids=[a['cbf_id'] for a in selected], current_label_ids_without_recent_appearance=sorted(current-set(players)),
            latest_historical_starting_ids=starting_ids, latest_lineup_source=latest['source_url'] if latest else None,
            current_starting_eleven_verified=False, quality_flags=flags, conflicting_label_ids=conflicting, installed=False))
    output = dict(cutoff='2026-11-04', prepared_at_utc=datetime.now(timezone.utc).isoformat(), clubs=clubs,
                  status='draft_requires_review_not_installable', installed=False)
    (root / 'domestic_squad_candidates.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print('clubs:',len(clubs),'selected candidates:',sum(len(c['draft_squad_ids']) for c in clubs))


if __name__ == '__main__':
    main()
