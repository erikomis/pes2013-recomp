#!/usr/bin/env python3
"""Inventory downloaded kit slots. Slot names are not visual validation."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    base=ROOT/'analysis/visual-2026/sources/kitpackAB2026/extracted/uniformes/kit-server'
    rows=[]
    for folder in sorted(base.glob('*/*')):
        if not folder.is_dir():continue
        slots=[]
        for slot in ('p1','p2'):
            config=folder/slot/'config.txt'
            values={}
            if config.exists():
                for line in config.read_text(encoding='utf-8-sig').splitlines():
                    line=line.split(';',1)[0].strip()
                    if '=' in line:
                        key,value=line.split('=',1);values[key.strip()]=value.strip()
            name=values.get('KitFile','')
            if name and Path(name).name!=name:raise ValueError('Nonlocal KitFile')
            texture=folder/slot/(name+'.ftex')
            data=texture.read_bytes() if name and texture.exists() else b''
            slots.append(dict(slot=slot,config=str(config.relative_to(ROOT)),kit_file=name,
                              texture=str(texture.relative_to(ROOT)),exists=bool(data),
                              ftex_magic=data[:4]==b'FTEX',bytes=len(data),
                              sha256=hashlib.sha256(data).hexdigest() if data else None,
                              role='home_candidate' if slot=='p1' else 'away_candidate',
                              visually_verified=False,ps3_ready=False))
        order=(folder/'order.ini').read_text(encoding='utf-8-sig').splitlines()
        default=[]
        for line in order:
            line=line.strip()
            if line.startswith('['):break
            if line and not line.startswith(';'):default.append(line)
        rows.append(dict(club=folder.name,division=folder.parent.name[-1],
                         default_order=default,order_differs=default[:2]!=['p1','p2'],slots=slots))
    result=dict(clubs=rows,total_clubs=len(rows),
                valid_texture_slots=sum(s['exists'] and s['ftex_magic'] for c in rows for s in c['slots']),
                note='Downloaded FTEX files only. Home/away visual review and PS3 conversion pending.')
    out=ROOT/'analysis/visual-2026/coverage/kit_slots.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='clubs'}))

if __name__=='__main__':main()
