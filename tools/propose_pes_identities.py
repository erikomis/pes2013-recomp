#!/usr/bin/env python3
"""Create name-only review candidates, never approve identities or edit saves."""
import argparse
import json
import unicodedata
from collections import defaultdict
from pathlib import Path


def normalize(name):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in
                           unicodedata.normalize('NFKD', name).upper()
                           if not unicodedata.combining(c)).split())


def propose(squads, database):
    by_name = defaultdict(dict)
    for player in database['players']:
        if not player['id']:
            continue
        for key in ('name', 'shirt_name'):
            name = normalize(player[key])
            if name:
                by_name[name][player['id']] = player
    rows = []
    for club in squads['clubs']:
        selected = {str(pid) for pid in club['draft_squad_ids']}
        for athlete in club['athletes']:
            if str(athlete['cbf_id']) not in selected:
                continue
            hits = {}
            for key in ('name', 'display_name'):
                for pid, player in by_name.get(normalize(athlete.get(key, '')), {}).items():
                    hits[pid] = dict(pes_id=pid, pes_name=player['name'],
                                     pes_shirt_name=player['shirt_name'])
            rows.append(dict(club=club['name'], cbf_id=athlete['cbf_id'],
                             name=athlete['name'], display_name=athlete['display_name'],
                             candidates=list(hits.values()), identity_verified=False,
                             face_id=None))
    return dict(status='name-only proposals; homonyms and 2013 age gap require review',
                installed=False, rows=rows,
                summary=dict(total=len(rows), unique_name_candidate=sum(len(r['candidates']) == 1 for r in rows),
                             ambiguous=sum(len(r['candidates']) > 1 for r in rows),
                             unmatched=sum(not r['candidates'] for r in rows)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('squads', type=Path)
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    print(json.dumps(propose(json.loads(args.squads.read_text()),
                             json.loads(args.database.read_text())), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
