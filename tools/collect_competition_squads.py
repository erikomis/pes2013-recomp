#!/usr/bin/env python3
"""Cache 2026 roster references for the expanded competition manifest; never edit saves."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.request import urlopen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    root = args.manifest.parent
    cache = root / 'rosters'
    cache.mkdir(exist_ok=True)
    manifest = json.loads(args.manifest.read_text())
    existing = {str(c['cbf_id']): c for c in json.loads(Path('analysis/brasil_2026_candidate_squads.json').read_text())['clubs']}
    result = dict(season=2026, collected_at=datetime.now(timezone.utc).isoformat(),
                  installed=False, status='references_not_installable', clubs=[], errors=[])
    failures = 0
    for club in manifest['clubs']:
        record = dict(club_key=club['key'], name=club['name'], max_players=32,
                      lineup_verified=False, pes_ids_verified=False)
        if str(club.get('cbf_id')) in existing:
            b = existing[str(club['cbf_id'])]
            selected = set(map(str, b['draft_squad_ids']))
            record.update(status='existing_AB_draft', athletes=[a for a in b['athletes'] if str(a['cbf_id']) in selected],
                          source_path='analysis/brasil_2026_candidate_squads.json')
        elif not club.get('espn_id'):
            record.update(status='pending_source_identity', athletes=[])
        else:
            team = club['espn_id']
            league = 'conmebol.libertadores' if 'libertadores' in club['competitions'] else 'conmebol.sudamericana'
            url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team}/roster?season=2026'
            target = cache / f'{team}.json'
            try:
                if not target.exists():
                    if args.offline or failures >= 3:
                        raise ValueError('not cached; network disabled after failures or offline flag')
                    time.sleep(1)
                    with urlopen(url, timeout=20) as response:
                        raw = response.read(8 * 1024 * 1024)
                    data = json.loads(raw)
                    if data.get('season', {}).get('year') != 2026 or str(data.get('team', {}).get('id')) != team:
                        raise ValueError('wrong roster year or team')
                    target.write_bytes(raw)
                data = json.loads(target.read_text())
                if data.get('season', {}).get('year') != 2026 or str(data.get('team', {}).get('id')) != team:
                    raise ValueError('wrong cached roster year or team')
                athletes = [dict(espn_id=str(a['id']), name=a['fullName'], display_name=a.get('displayName'),
                                 shirt_number=a.get('jersey'), position=a.get('position', {}).get('name'),
                                 birth_date=(a.get('dateOfBirth') or '')[:10], identity_verified=False,
                                 current_club_verified=False, pes_player_id=None, face_id=None)
                            for a in data.get('athletes', [])]
                if not athletes:
                    raise ValueError('empty roster')
                record.update(status='reference_requires_current_club_and_recent_lineup_checks', athletes=athletes,
                              source_url=url, source_timestamp=data.get('timestamp'), selected_ids=[],
                              selection_status='pending_professional_and_recent_match_evidence')
                failures = 0
                print(f"{club['name']}: {len(athletes)} references", flush=True)
            except Exception as exc:
                failures += 1
                record.update(status='pending_collection', athletes=[])
                result['errors'].append(dict(club_key=club['key'], error=str(exc)))
                print(f"{club['name']}: {exc}", flush=True)
        result['clubs'].append(record)
        (root / 'squad_references.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('clubs:', len(result['clubs']), 'errors:', len(result['errors']))


if __name__ == '__main__':
    main()
