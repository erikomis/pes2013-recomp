#!/usr/bin/env python3
"""Summarize competition preparation without changing participant identities or saves."""
from collections import Counter
import csv
import json
from pathlib import Path


def main():
    root = Path('analysis/competitions-2026')
    participants = json.loads((root / 'participants.json').read_text())
    mapping = {m['club_key']: m for m in json.loads((root / 'cbf_identity_map.json').read_text())}
    domestic = {c['club_key']: c for c in json.loads((root / 'domestic_squad_candidates.json').read_text())['clubs']}
    references = {c['club_key']: c for c in json.loads((root / 'squad_references.json').read_text())['clubs']}
    lineups = json.loads((root / 'domestic_lineup_evidence.json').read_text())
    rows = []
    for c in participants['clubs']:
        key = c['key']
        d = domestic.get(key)
        ref = references[key]
        rows.append(dict(club_key=key, name=c['name'], country=c['country'], state=c['state'],
            competitions=','.join(c['competitions']), cbf_id=mapping.get(key, {}).get('cbf_id', c['cbf_id']),
            roster_status=d['status'] if d else ref['status'],
            selected_candidates=len(d['draft_squad_ids']) if d else len(ref['athletes']) if ref['status']=='existing_AB_draft' else 0,
            reference_players=len(d['athletes']) if d else len(ref['athletes']),
            latest_match_date=d['latest_match_date'] if d else None,
            latest_match_age_days=d['latest_match_age_days'] if d else None,
            quality_flags=';'.join(d['quality_flags']) if d else 'existing_draft_review' if ref['status']=='existing_AB_draft' else 'current_club_and_selection_pending',
            current_starting_eleven_verified=False, installed=False))
    assert len(rows)==203 and len({r['club_key'] for r in rows})==203
    assert all(0 <= r['selected_candidates'] <= 32 for r in rows)
    stats = dict(unique_clubs=len(rows), statuses=dict(Counter(r['roster_status'] for r in rows)),
        domestic_additional_clubs=len(domestic), domestic_candidates=sum(len(c['draft_squad_ids']) for c in domestic.values()),
        domestic_matches_collected=lineups['match_count'], match_errors=len(lineups['errors']),
        domestic_with_at_least_18_candidates=sum(len(c['draft_squad_ids'])>=18 for c in domestic.values()),
        domestic_flags=dict(Counter(f for c in domestic.values() for f in c['quality_flags'])), installed=False)
    (root / 'preparation_status.json').write_text(json.dumps(dict(summary=stats,clubs=rows),ensure_ascii=False,indent=2)+'\n')
    with (root / 'preparation_status.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
