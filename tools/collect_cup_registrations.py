#!/usr/bin/env python3
"""Match the official 2026 Copa directory by name/state and cache registrations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from collect_cbf_rosters import athletes_from_html, fetch, normalize_club
from collect_recent_squads import payload

# Explicit Annex A short-name -> official directory identity, checked with UF.
ALIASES = {
    ('Barra', 'SC'): '40387', ('Vasco', 'AC'): '20292',
    ('Atlético Alagoinhas', 'BA'): '20236', ('Porto', 'BA'): '62328',
    ('Porto Vitória', 'ES'): '53162', ('Rio Branco', 'ES'): '62546',
    ('Betim', 'MG'): '34709', ('FC Pantanal', 'MS'): '63954',
    ('Ivinhema', 'MS'): '21817', ('Operário VG', 'MT'): '35079',
    ('Primavera', 'MT'): '59905', ('Botafogo', 'PB'): '63524',
    ('Serra Branca', 'PB'): '37846', ('Cianorte', 'PR'): '20816',
    ('Maringá', 'PR'): '21918', ('ABC', 'RN'): '20042',
    ('América', 'RN'): '62025', ('Guaporé', 'RO'): '53757',
    ('Porto Velho', 'RO'): '56220', ('GAS', 'RR'): '20353',
    ('Guarany de Bagé', 'RS'): '20225', ('Santa Catarina', 'SC'): '39727',
    ('América', 'SE'): '20151', ('Lagarto', 'SE'): '35680',
    ('Araguaína', 'TO'): '21745', ('Capital', 'TO'): '38081',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('analysis/competitions-2026'))
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    root = args.root
    manifest = json.loads((root / 'participants.json').read_text())
    directory = json.loads((root / 'sources/cbf-copa-clubs.json').read_text())
    cache = root / 'cbf-clubs'
    cache.mkdir(exist_ok=True)
    mappings = []
    for club in manifest['clubs']:
        if club['country'] != 'BRA':
            continue
        expected = club.get('cbf_id') or ALIASES.get((club['name'], club['state']))
        matches = [s for s in directory
                   if s['name'].rsplit('-', 1)[-1].strip() == club['state'] and
                   (s['cbf_id'] == expected if expected else normalize_club(s['name']) == normalize_club(club['name']))]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous or missing CBF identity: {club['key']}")
        m = dict(club_key=club['key'], **matches[0], reused_AB=bool(club['roster_reference']))
        mappings.append(m)
    assert len(mappings) == 126 and len({m['cbf_id'] for m in mappings}) == 126
    (root / 'cbf_identity_map.json').write_text(json.dumps(mappings, ensure_ascii=False, indent=2) + '\n')
    result = dict(season=2026, requested_cutoff='2026-11-04',
                  collected_at_utc=datetime.now(timezone.utc).isoformat(),
                  installed=False, status='registration_references_not_selected_squads', clubs=[], errors=[])
    failures = 0
    for m in mappings:
        if m['reused_AB']:
            continue
        path = cache / f"{m['cbf_id']}.html"
        try:
            if not path.exists():
                if args.offline or failures >= 3:
                    raise ValueError('Not cached; offline or stopped after three failures')
                time.sleep(1)
            raw = fetch(m['url'], path)
            page = payload(raw, 'jogos')
            if (str(page.get('campeonato', {}).get('exercicio')) != '2026'
                    or not any(str(t.get('time_id')) == m['cbf_id'] for t in page.get('time', []))):
                raise ValueError('CBF returned the wrong club or season')
            athletes = []
            for a in athletes_from_html(raw):
                current = (normalize_club(a['clube_nome_popular']) == normalize_club(m['name'])
                           and a.get('clube_uf') == m['name'].rsplit('-', 1)[-1].strip())
                athletes.append(dict(cbf_id=str(a['atleta_id']), name=a['atleta_nome'],
                                     display_name=a['Atleta_apelido'], current_club=a['clube_nome_popular'],
                                     current_club_state=a.get('clube_uf'), registration_matches_club=current,
                                     professional_verified=False, position=None, shirt_number=None,
                                     pes_player_id=None, face_id=None))
            result['clubs'].append(dict(**m, source_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                                        athletes=athletes, selected_ids=[], max_players=32,
                                        selection_status='pending_recent_professional_match_evidence'))
            failures = 0
            print(f"{m['name']}: {len(athletes)} registrations, {sum(a['registration_matches_club'] for a in athletes)} matching current club", flush=True)
        except Exception as exc:
            failures += 1
            result['errors'].append(dict(club_key=m['club_key'], cbf_id=m['cbf_id'], error=str(exc)))
            print(f"{m['name']}: {exc}", flush=True)
        (root / 'cbf_registrations.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Collected:', len(result['clubs']), 'Errors:', len(result['errors']))


if __name__ == '__main__':
    main()
