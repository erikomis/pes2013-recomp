#!/usr/bin/env python3
"""Collect dated professional match evidence for additional Copa do Brasil clubs."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import time
from urllib.request import urlopen

from collect_cbf_rosters import fetch
from collect_recent_squads import payload, match_evidence, slug


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('analysis/competitions-2026'))
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    root = args.root
    cutoff = date(2026, 11, 4)
    clubs = [c for c in json.loads((root / 'cbf_identity_map.json').read_text()) if not c['reused_AB']]
    directories = [c for div in ('c', 'd') for c in json.loads((root / f'sources/serie-{div}.json').read_text())]
    cache = root / 'domestic-lineups'
    cache.mkdir(exist_ok=True)
    errors, wanted, club_games = [], {}, {}
    failures = 0
    for club in clubs:
        club_id = club['cbf_id']
        sources = [(root / f'cbf-clubs/{club_id}.html', club['url'], 'copa-do-brasil/masculino')]
        for entry in directories:
            if entry['cbf_id'] == club_id:
                sources.append((cache / f"club-{club_id}-{entry['division']}.html", entry['url'],
                                f"campeonato-brasileiro/serie-{entry['division']}"))
        games = {}
        for path, url, route in sources:
            try:
                if not path.exists():
                    if args.offline or failures >= 3:
                        raise ValueError('Not cached; network disabled')
                    time.sleep(1)
                raw = fetch(url, path)
                data = payload(raw, 'jogos')
                if str(data['campeonato']['exercicio']) != '2026' or not any(str(t['time_id']) == club_id for t in data['time']):
                    raise ValueError('Wrong club or season in CBF page')
                for game in data['jogos']:
                    played = datetime.strptime(game['data'].strip(), '%d/%m/%Y').date()
                    if played > cutoff or played.year != 2026:
                        continue
                    if club_id not in {str(game[s]['id']) for s in ('mandante', 'visitante')}:
                        raise ValueError('Unrelated match in club page')
                    match_id = str(game['id_jogo'])
                    names = slug(game['mandante']['nome']) + '-x-' + slug(game['visitante']['nome'])
                    match_url = f'https://www.cbf.com.br/futebol-brasileiro/jogos/{route}/2026/{names}/{match_id}?view=escalacao'
                    games[match_id] = dict(match_id=match_id, date=played.isoformat(), url=match_url,
                                          competition=data['campeonato'])
                failures = 0
            except Exception as exc:
                failures += 1
                errors.append(dict(club_key=club['club_key'], source_url=url, error=str(exc)))
        recent = sorted(games.values(), key=lambda g: (g['date'], g['match_id']), reverse=True)[:3]
        club_games[club['club_key']] = recent
        wanted.update({g['match_id']: g for g in recent})
        print(f"Fixtures {club['name']}: latest {recent[0]['date'] if recent else 'missing'}", flush=True)
    dump(root / 'domestic_match_queue.json', dict(clubs=club_games, matches=list(wanted.values()), errors=errors))
    matches = {}
    failures = 0
    for index, (mid, game) in enumerate(wanted.items(), 1):
        path = cache / f'match-{mid}.json'
        try:
            if path.exists():
                match = json.loads(path.read_text())
            else:
                if args.offline or failures >= 3:
                    raise ValueError('Not cached; network disabled')
                time.sleep(1)
                with urlopen(game['url'], timeout=20) as response:
                    raw = response.read().decode()
                match = match_evidence(raw, game['url'], game['date'], mid)
                dump(path, match)
            if match['match_id'] != mid or match['date'] != game['date']:
                raise ValueError('Cached match identity/date mismatch')
            matches[mid] = match
            failures = 0
        except Exception as exc:
            failures += 1
            errors.append(dict(match_id=mid, source_url=game['url'], error=str(exc)))
        print(f'Matches {index}/{len(wanted)}; collected {len(matches)}', flush=True)
    output = []
    for club in clubs:
        ids = [g['match_id'] for g in club_games[club['club_key']]]
        evidence = []
        for mid in ids:
            match = matches.get(mid)
            if not match:
                continue
            for team in match['teams']:
                if team['cbf_id'] == club['cbf_id']:
                    evidence.append(dict(match_id=mid, date=match['date'], source_url=match['source_url'],
                                         starters=[a for a in team['athletes'] if a['started']],
                                         substitutes=[a for a in team['athletes'] if not a['started']]))
        latest = evidence[0]['date'] if evidence else None
        output.append(dict(club_key=club['club_key'], cbf_id=club['cbf_id'], name=club['name'],
                           matches=evidence, latest_match_date=latest,
                           age_days=(cutoff - date.fromisoformat(latest)).days if latest else None,
                           reference_scope='Copa do Brasil and Serie C/D only; state/regional matches not checked',
                           current_lineup_verified=False, installed=False))
    dump(root / 'domestic_lineup_evidence.json', dict(cutoff=cutoff.isoformat(), clubs=output,
         match_count=len(matches), errors=errors, installed=False,
         status='dated_match_evidence_not_current_lineup_or_selected_squad'))


if __name__ == '__main__':
    main()
