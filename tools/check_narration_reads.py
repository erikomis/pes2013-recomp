"""check_narration_reads.py <boot.log with FS_IO_LOG=dt00_b> <EEDIT DATA.BIN> <inventory.json> <team name>...: which player-name clips
(B_VP_P0_R<id>) the game read from dt00_b during the run, and whose they are among the named teams."""
import sys, json, re, struct, bisect
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pes2013_edit as e
log, edit, inv, teams = sys.argv[1], sys.argv[2], sys.argv[3], [t.upper() for t in sys.argv[4:]]
ent = [x for x in json.load(open(inv))['entries'] if x['size']]
offs = [x['offset'] for x in ent]
reads = []
for m in re.finditer(r'\[fsio\] [RA] fd=\d+ pos=0x([0-9A-F]+) want=(\d+) got=(\d+)', open(log, errors='ignore').read()):
    pos = int(m.group(1), 16); i = bisect.bisect_right(offs, pos) - 1
    if i >= 0 and pos < ent[i]['offset'] + ent[i]['size']: reads.append(ent[i])
clips = {}
for x in reads:
    m = re.match(r'B_VP_P0_R(\d+)', x.get('internal_name') or '')
    if m: clips[int(m.group(1))] = clips.get(int(m.group(1)), 0) + 1
print(len(reads), 'clip reads,', len(clips), 'distinct player-name clips')
raw = open(edit, 'rb').read(); d = e.decode(raw)
pl = {p['id']: p for p in d['players']}
call = {pid: struct.unpack_from('>H', raw, p['offset'] + 114)[0] for pid, p in pl.items()}
owner = {}
for t in d['teams']:
    if t['name'].upper() in teams and t.get('roster'):
        for m in t['roster']['members']:
            owner.setdefault(call.get(m['player_id']), []).append((t['name'], m['name'], m['player_id']))
hit = 0
for cid, n in sorted(clips.items()):
    who = owner.get(cid)
    if who: hit += 1
    print(f'R{cid:05d} x{n}: ' + ('; '.join(f'{a} {b} (id {c})' for a, b, c in who) if who else 'not a player of these teams'))
print(hit, 'of', len(clips), 'clips belong to players of', ', '.join(teams))
for t in d['teams']:
    if t['name'].upper() in teams and t.get('roster'):
        ms = t['roster']['members']
        print(t['name'], len(ms), 'players,', sum(1 for m in ms if call.get(m['player_id']) != 0xFFFF), 'with a name clip')
