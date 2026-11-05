#!/usr/bin/env python3
"""Stage a Flamengo name/number prototype with all existing visual saves.

Preserves legacy attributes/faces. Never installs into the owner's profile.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
from pes2013_edit import decode, crc32

ROOT = Path(__file__).resolve().parents[1]


def field(data, offset, size, text):
    value = text.upper().encode('utf-8')
    if len(value) >= size:
        raise ValueError(f'Name too long: {text}')
    data[offset:offset + size] = value + bytes(size - len(value))


def main():
    source = ROOT / 'rpcs3/dev_hdd0/home/00000001/savedata'
    dest = ROOT / 'analysis/test-save-flamengo-2026'
    if dest.exists():
        raise SystemExit('Test profile already exists; refusing to overwrite it')
    original = (source / 'BLUS31029EEDIT/DATA.BIN').read_bytes()
    decoded = decode(original)
    reference = json.loads((ROOT / 'analysis/brasil-2026-review/flamengo_professional_reference.json').read_text())
    roster = next(r for r in decoded['rosters'] if r['team_id'] == 1248)
    players = {p['id']: p for p in decoded['players']}
    by_name = {p['display_name']: p for p in reference['players']}
    # Preserve the existing formation's slot order. Roles/attributes are legacy,
    # not a claim of verified 2026 positions, ratings, appearances or starting XI.
    names = ['Rossi', 'Léo Pereira', 'Léo Ortiz', 'Varela', 'Ayrton Lucas',
             'Erick Pulgar', 'Jorginho', 'De Arrascaeta', 'Luiz Araújo',
             'L. Paquetá', 'Pedro', 'Andrew', 'Dyogo Alves', 'Danilo',
             'João Victor', 'Vitão', 'Alex Sandro', 'De La Cruz',
             'Evertton Araujo', 'Saúl', 'G. Plata', 'Emerson Royal',
             'Carrascal', 'Samuel Lino', 'Joaquín Freitas',
             'Anthony Valencia', 'Bruno Henrique']
    assert len(names) == len(roster['members']) == 27
    assert set(names) == set(by_name)
    changed = bytearray(original)
    manifest = []
    allowed = set(range(8, 12))
    for member, name in zip(roster['members'], names):
        player = players[member['player_id']]
        actual = by_name[name]
        for relative, length in [(50, 46), (96, 18)]:
            start = player['offset'] + relative
            field(changed, start, length, name)
            allowed.update(range(start, start + length))
        number_offset = roster['offset'] + 132 + member['slot']
        changed[number_offset] = actual['shirt_number']
        allowed.add(number_offset)
        manifest.append(dict(pes_id=player['id'], cbf_id=actual['cbf_id'],
                             previous_name=player['name'], test_name=name,
                             shirt_number=actual['shirt_number'],
                             attributes='legacy placeholder', face='legacy placeholder'))
    struct.pack_into('>I', changed, 8, crc32(changed))
    validated = decode(changed)
    assert all(i in allowed for i, (a, b) in enumerate(zip(original, changed)) if a != b)
    assert len(validated['players']) == len(decoded['players'])
    target = dest / 'gamedata/dev_hdd0/home/00000001/savedata'
    shutil.copytree(source, target)
    (target / 'BLUS31029EEDIT/DATA.BIN').write_bytes(changed)
    (dest / 'hdd1/cache').mkdir(parents=True)
    (dest / 'manifest.json').write_text(json.dumps(dict(
        status='experimental names/numbers only; not gameplay validated',
        scope='Flamengo domestic roster, 27 players; other clubs remain legacy',
        shared_id_warning='Names may also appear in national/continental rosters referencing these legacy IDs',
        original_sha256=hashlib.sha256(original).hexdigest(),
        test_sha256=hashlib.sha256(changed).hexdigest(),
        sources=reference['sources'], changes=manifest,
        faces_updated=False, attributes_updated=False,
        ps3_console_package=False, param_pfd_resigned=False), ensure_ascii=False, indent=2))
    assert (source / 'BLUS31029EEDIT/DATA.BIN').read_bytes() == original
    print(dest)


if __name__ == '__main__':
    main()
