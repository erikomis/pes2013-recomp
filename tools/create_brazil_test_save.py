#!/usr/bin/env python3
"""Create an isolated names/numbers/roster prototype for mapped Brazilian clubs.

Legacy player records supply IDs and attributes; this is not an identity/face
transfer. No league tables, unknown attributes or original saves are modified.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from pes2013_edit import decode, crc32

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fit_name(text, size):
    value = text.upper().strip()
    while len(value.encode('utf-8')) >= size:
        value = value[:-1]
    if not value:
        raise ValueError('Empty name')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-clubs', action='store_true',
                        help='Use explicitly checked generic slots for the remaining 13 clubs')
    args = parser.parse_args()
    source = ROOT / 'rpcs3/dev_hdd0/home/00000001/savedata'
    dest = ROOT / ('analysis/test-save-brasil-40-2026' if args.all_clubs else 'analysis/test-save-brasil-2026')
    if dest.exists():
        raise SystemExit('Destination exists; refusing to replace a test profile')
    data = (source / 'BLUS31029EEDIT/DATA.BIN').read_bytes()
    before = decode(data)
    reference_path = ROOT / 'analysis/brasil_2026_candidate_squads.json'
    references = json.loads(reference_path.read_text())
    clubs = {c['cbf_id']: c for c in references['clubs']}
    mapping_path = ROOT / 'analysis/brasil-2026-review/team_mapping.json'
    mapping = json.loads(mapping_path.read_text())
    teams = {t['id']: t for t in before['teams']}
    replacements = []
    if args.all_clubs:
        generic_names = ['TERZAMOC', 'CHEQUEBERO', 'NAHUANOZEM', 'PUNTIHUERVA',
                         'DUZAGHALIA', 'WAHUCHAMATE', 'QUIMRIGNA', 'HUATYNCAN',
                         'CUNTURIPA', 'GIMARQUELLA', 'ARUZUTANQUE', 'QUERTEMOYO', 'JOBAZAVAR']
        unmapped = [m for m in mapping if m['pes_team_id'] is None]
        if len(unmapped) != len(generic_names):
            raise ValueError('Expected exactly 13 unmapped clubs')
        for index, (m, old_name) in enumerate(zip(unmapped, generic_names)):
            team = teams[2470+index]
            if team['name'] != old_name or not team['roster']:
                raise ValueError('Generic slot differs from inspected source')
            m['pes_team_id'] = team['id']
            replacements.append(dict(cbf_id=m['cbf_id'], team_id=team['id'],
                old_name=old_name, new_name=m['name'].split('  - ')[0].strip(),
                team_name_offset=team['offset'], league_reassigned=False))
    rosters = {r['team_id']: r for r in before['rosters']}
    players = {p['id']: p for p in before['players']}
    planned, pending, used_cbf = [], [], set()
    for m in mapping:
        if m['pes_team_id'] is None:
            pending.append(dict(club=m['name'], reason='unmapped_team_slot'))
            continue
        club = clubs[m['cbf_id']]
        athletes = [a for a in club['athletes'] if a['current_registration_confirmed']]
        if not 11 <= len(athletes) <= 32:
            raise ValueError('Unexpected squad size')
        # First keeper, then recent starters, then remaining players. This does
        # not imply a valid modern formation: positions remain legacy.
        keepers = [a for a in athletes if a['goalkeeper']]
        if not keepers:
            raise ValueError('No keeper evidence')
        first = next((a for a in keepers if a['started']), keepers[0])
        athletes = [first] + sorted([a for a in athletes if a is not first],
                                  key=lambda a: (a['goalkeeper'], not a['started']))
        for a in athletes:
            if a['cbf_id'] in used_cbf or not 0 <= a['shirt_number'] <= 255:
                raise ValueError('Duplicate identity or invalid number')
            used_cbf.add(a['cbf_id'])
        roster = rosters[m['pes_team_id']]
        planned.append(dict(mapping=m, athletes=athletes, roster=roster,
                            old_ids=[p['player_id'] for p in roster['members']]))
    all_ids = [pid for p in planned for pid in p['old_ids']]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('Shared player IDs among target clubs')
    spare = [pid for p in planned for pid in p['old_ids'][len(p['athletes']):]]
    required = sum(max(0, len(p['athletes'])-len(p['old_ids'])) for p in planned)
    if required > len(spare):
        raise ValueError('Insufficient existing target-player records')
    external = defaultdict(list)
    targets = {p['roster']['team_id'] for p in planned}
    for r in before['rosters']:
        if r['team_id'] not in targets:
            for a in r['members']:
                external[a['player_id']].append(r['team_id'])
    changed, allowed, changes = bytearray(data), bytearray(len(data)), []
    allowed[8:12] = b'\1'*4
    for replacement in replacements:
        name = fit_name(replacement['new_name'], 72)
        start = replacement['team_name_offset']
        raw = name.encode('utf-8')
        changed[start:start+72] = raw+bytes(72-len(raw))
        allowed[start:start+72] = b'\1'*72
        replacement['written_name'] = name
    for plan in planned:
        roster, athletes = plan['roster'], plan['athletes']
        ids = plan['old_ids'][:len(athletes)]
        while len(ids) < len(athletes):
            ids.append(spare.pop(0))
        offset = roster['offset']
        allowed[offset+4:offset+164] = b'\1'*160
        struct.pack_into('>32I', changed, offset+4, *(ids+[0]*(32-len(ids))))
        changed[offset+132:offset+164] = bytes(32)
        assignments = []
        for index, (pid, athlete) in enumerate(zip(ids, athletes)):
            player = players[pid]
            written = {}
            for relative, size, label in [(50,46,'name'), (96,18,'shirt_name')]:
                name = fit_name(athlete['display_name'], size)
                raw = name.encode('utf-8')
                start = player['offset']+relative
                changed[start:start+size] = raw+bytes(size-len(raw))
                allowed[start:start+size] = b'\1'*size
                written[label] = name
            changed[offset+132+index] = athlete['shirt_number']
            assignments.append(dict(pes_id=pid, cbf_id=athlete['cbf_id'],
                reference_name=athlete['display_name'], previous_name=player['name'],
                shirt_number=athlete['shirt_number'], **written,
                evidence=athlete['evidence'], other_rosters_using_id=external[pid],
                attributes_and_face='legacy placeholder', identity_binding_verified=False))
        counts = Counter(a['shirt_number'] for a in athletes)
        changes.append(dict(club=plan['mapping']['name'], team_id=roster['team_id'],
            division_reference=plan['mapping']['division'], assignments=assignments,
            duplicate_shirt_numbers=[n for n,c in counts.items() if c>1]))
    struct.pack_into('>I', changed, 8, crc32(changed))
    after = decode(changed)
    if any(a != b and not allowed[i] for i,(a,b) in enumerate(zip(data, changed))):
        raise ValueError('Unexpected byte mutation')
    if [(p['id'],p['offset']) for p in after['players']] != [(p['id'],p['offset']) for p in before['players']]:
        raise ValueError('Player layout changed')
    out_rosters = {r['team_id']:r for r in after['rosters']}
    out_players = {p['id']:p for p in after['players']}
    out_teams = {t['id']:t for t in after['teams']}
    for replacement in replacements:
        assert out_teams[replacement['team_id']]['name'] == replacement['written_name']
    for c in changes:
        members = out_rosters[c['team_id']]['members']
        assert len(members) == len(c['assignments'])
        for member,a in zip(members,c['assignments']):
            assert member['player_id'] == a['pes_id'] and member['shirt_number'] == a['shirt_number']
            assert out_players[a['pes_id']]['name'] == a['name']
    target = dest / 'gamedata/dev_hdd0/home/00000001/savedata'
    shutil.copytree(source, target)
    (target / 'BLUS31029EEDIT/DATA.BIN').write_bytes(changed)
    (dest / 'hdd1/cache').mkdir(parents=True)
    copied = 0
    for path in source.rglob('*'):
        if path.is_file() and path.relative_to(source).as_posix() != 'BLUS31029EEDIT/DATA.BIN':
            if digest(path.read_bytes()) != digest((target/path.relative_to(source)).read_bytes()):
                raise ValueError('Copied resource differs')
            copied += 1
    assert (source / 'BLUS31029EEDIT/DATA.BIN').read_bytes() == data
    manifest = dict(status='experimental names/numbers/rosters; not gameplay validated',
        source_sha256=digest(data), output_sha256=digest(changed),
        reference_sha256=digest(reference_path.read_bytes()), mapping_sha256=digest(mapping_path.read_bytes()),
        cutoff=references['cutoff'], clubs_updated=len(changes), players_named=len(used_cbf),
        changes=changes, pending_clubs=pending, faces_updated=False, kits_updated=False,
        generic_slot_replacements=replacements,
        positions_updated=False, attributes_updated=False, league_membership_updated=False,
        warning='Legacy IDs repurposed: other rosters sharing them inherit names. Formation and appearances remain old.',
        ps3_console_package=False, param_pfd_resigned=False)
    (dest / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    validation = dict(crc_valid=True, allowed_byte_changes_only=True, player_ids_preserved=True,
        roster_names_numbers_roundtrip=True, original_unchanged=True, copied_resources_verified=copied,
        game_load_verified=False)
    (dest / 'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(dict(profile=str(dest), clubs=len(changes), players=len(used_cbf), pending=len(pending), **validation)))


if __name__ == '__main__':
    main()
