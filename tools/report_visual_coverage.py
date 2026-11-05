#!/usr/bin/env python3
"""Track requested A/B visual assets without equating name matches with identity."""
import csv,json,re,zipfile
from pathlib import Path
from propose_pes_identities import normalize
ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'analysis/visual-2026/sources'
    squads=json.loads((ROOT/'analysis/brasil_2026_candidate_squads.json').read_text())
    faces=[]
    for archive in sorted(source.glob('*.zip')):
        if not zipfile.is_zipfile(archive):continue
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                base=Path(entry.filename).name
                if not re.search(r'face.*\.bin$',base,re.I):continue
                name=re.split(r'[_ -]*face',base,flags=re.I)[0]
                faces.append(dict(archive=archive.name,file=entry.filename,name=name,normalized=normalize(name)))
    clubs=[];athletes=[]
    for club in squads['clubs']:
        selected={str(i) for i in club['draft_squad_ids']}
        people=[]
        for player in club['athletes']:
            if str(player['cbf_id']) not in selected:continue
            aliases={normalize(player['name']),normalize(player['display_name'])}
            candidates=[f for f in faces if f['normalized'] in aliases]
            row=dict(club_id=club['cbf_id'],club=club['name'],cbf_id=player['cbf_id'],name=player['name'],
                     display_name=player['display_name'],face_candidates=candidates,
                     identity_verified=False,face_ps3_ready=False)
            people.append(row);athletes.append(row)
        clubs.append(dict(cbf_id=club['cbf_id'],name=club['name'],division=club['division'],
                          selected_players=len(people),players_with_name_candidates=sum(bool(p['face_candidates']) for p in people),
                          faces_identity_verified=0,faces_ps3_ready=0,home_kit='not_obtained',away_kit='not_obtained',
                          complete=False))
    output=ROOT/'analysis/visual-2026/coverage';output.mkdir(exist_ok=True)
    kit_path=output/'kit_slots.json'
    if kit_path.exists():
        kit_rows=json.loads(kit_path.read_text())['clubs']
        by_key={(k['division'],normalize(k['club'])):k for k in kit_rows}
        aliases={'61377':'EC Bahia','20011':'SC Internacional','59897':'America Mineiro',
                 '56654':'Botafogo Sp','31514':'Novorizontino','31790':'Sao Bernado',
                 '20010':'Sport','20008':'Santos'}
        used=set()
        for club in clubs:
            name=aliases.get(club['cbf_id'])
            if name is None:
                name=re.sub(r'\s*-\s*[A-Z]{2}\s*$', '', club['name'])
                name=re.sub(r'\bSAF\b', '', name, flags=re.I).strip()
            key=(club['division'],normalize(name))
            if key not in by_key or key in used:raise ValueError(f'Unmapped/duplicate kit club: {club["name"]}')
            used.add(key)
            kit=by_key[key]
            for field,slot in [('home_kit','p1'),('away_kit','p2')]:
                item=next(i for i in kit['slots'] if i['slot']==slot)
                if item['exists'] and item['ftex_magic']:
                    club[field]='downloaded_candidate_not_converted'
            club['kit_source_club']=kit['club']

    (output/'coverage.json').write_text(json.dumps(dict(clubs=clubs,athletes=athletes,
        face_files=len(faces),complete=False,note='Name-only candidates; no downloaded assets installed'),ensure_ascii=False,indent=2))
    with (output/'clubs.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(clubs[0]));writer.writeheader();writer.writerows(clubs)
    report=['# Cobertura visual 2026','',
            'Meta: faces dos jogadores selecionados e uniformes 1/2 dos 40 clubes.',
            'Correspondência de nome é apenas candidata, não face confirmada. Nenhum recurso novo instalado.','',
            '| Clube | Série | Jogadores | Com candidato por nome | Faces PS3 prontas | Camisa 1 | Camisa 2 |',
            '|---|---|---:|---:|---:|---|---|']
    for c in clubs:report.append(f"| {c['name']} | {c['division']} | {c['selected_players']} | {c['players_with_name_candidates']} | 0 | {('Baixado; revisar/converter' if c['home_kit'] != 'not_obtained' else 'Pendente')} | {('Baixado; revisar/converter' if c['away_kit'] != 'not_obtained' else 'Pendente')} |")
    (ROOT/'docs/COBERTURA_VISUAL_2026.md').write_text('\n'.join(report)+'\n')
    print(json.dumps({'clubs':len(clubs),'selected_players':len(athletes),'face_files':len(faces),
                      'players_with_name_candidates':sum(bool(p['face_candidates']) for p in athletes),
                      'kits_required':80,'clubs_complete':0}))

if __name__=='__main__':main()
