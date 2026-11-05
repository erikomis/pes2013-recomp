#!/usr/bin/env python3
"""Extract cached official first-team cards; compare names without assigning PES IDs."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'analysis/competitions-2026'


class Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.parts = []
        self.players = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href', '')
        if tag == 'a' and href.startswith('/plantel/'):
            self.href, self.parts = href, []

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != 'a' or not self.href:
            return
        label = ' '.join(' '.join(self.parts).split())
        match = re.fullmatch(r'(\d+) \1 (Arquero|Defensor|Mediocampista|Delantero) (.+?) ›', label)
        if not match:
            raise ValueError(f'Unexpected card: {label}')
        number, position, name = match.groups()
        self.players.append(dict(name=name, shirt_number=int(number), position_group=position,
                                 official_url='https://csir.com.ar' + self.href))
        self.href = None


def normalized(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.casefold())
                   if not unicodedata.combining(c))


def main():
    source = BASE / 'official-clubs/rivadavia-plantel.html'
    parser = Cards()
    parser.feed(source.read_text())
    players = parser.players
    if not players or len(players) > 32 or len({p['official_url'] for p in players}) != len(players):
        raise ValueError('Unexpected roster size or duplicate cards')
    reference = json.loads((BASE / 'rosters/9744.json').read_text())
    used = set()
    for player in players:
        matches = [a for a in reference['athletes']
                   if normalized(a['displayName']) == normalized(player['name'])]
        player['espn_name_candidates'] = [dict(id=a['id'], name=a['displayName']) for a in matches]
        player['identity_verified'] = False
        player['pes_id'] = None
        used.update(a['id'] for a in matches)
    result = dict(club='Independiente Rivadavia', source_url='https://csir.com.ar/futbol?tab=plantel',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_effective_date=None, historical_cutoff_verified=False,
                  status='official_page_snapshot_not_installed',
                  note='Official live page has no roster effective date. Broad positions only; no starting XI inferred. '
                       'ESPN names absent from this page are not automatically departures.',
                  players=players,
                  espn_without_exact_official_name=[dict(id=a['id'], name=a['displayName'])
                      for a in reference['athletes'] if a['id'] not in used])
    out = BASE / 'official-clubs/rivadavia-roster-review.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(official_players=len(players), exact_name_matches=len(used),
                         unresolved_official_names=[p['name'] for p in players if not p['espn_name_candidates']],
                         unmatched_espn=len(result['espn_without_exact_official_name'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
