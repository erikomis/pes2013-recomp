#!/usr/bin/env python3
"""Build a local RGB inspection gallery for the downloaded A/B kit slots."""
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

import ftex_convert as fc


def main():
    source = Path('analysis/visual-2026/coverage/kit_slots.json')
    output = Path('analysis/visual-2026/kit-review')
    output.mkdir(exist_ok=True)
    records, cards, errors = [], [], []
    for club in json.loads(source.read_text())['clubs']:
        name = club['club']
        slug = re.sub('[^a-z0-9]+', '-', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()).strip('-')
        figures = []
        slots = list(club['slots'])
        # Include the pack's alternate first/second choices for visual comparison.
        base = Path(slots[0]['config']).parent.parent
        for extra in club['default_order'][:2]:
            if extra in {s['slot'] for s in slots}:
                continue
            if Path(extra).name != extra:
                raise ValueError('Nonlocal slot name')
            values = {}
            for line in (base / extra / 'config.txt').read_text(encoding='utf-8-sig').splitlines():
                line = line.split(';', 1)[0]
                if '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip()
            kit = values['KitFile']
            if Path(kit).name != kit:
                raise ValueError('Nonlocal KitFile')
            texture = base / extra / (kit + '.ftex')
            slots.append(dict(slot=extra, texture=str(texture), sha256=hashlib.sha256(texture.read_bytes()).hexdigest()))
        for slot in slots:
            try:
                path = Path(slot['texture'])
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != slot['sha256']:
                    raise ValueError('Source changed since inventory')
                info = fc.read_ftex(path)
                info['data'] = path.read_bytes()
                mip = fc.pick_mip(info, 512)
                rgba, w, h = fc.decode_frame_rgba(info, mip)
                if w > 512 and w == h:
                    rgba = fc.box_downscale(rgba, w, h, 512)
                    w = h = 512
                # Display RGB channels for texture inspection. Source alpha is
                # retained in the original FTEX; this PNG is never game input.
                pixels = bytearray(rgba)
                pixels[3::4] = b'\xff' * (w*h)
                png = fc.encode_png_rgba(pixels, w, h)
                filename = f"{club['division']}-{slug}-{slot['slot']}.png"
                (output / filename).write_bytes(png)
                record = dict(club=name, division=club['division'], slot=slot['slot'], source=str(path),
                    source_sha256=digest, native_width=info['width'], native_height=info['height'],
                    preview=filename, preview_width=w, preview_height=h, mip=mip,
                    png_sha256=hashlib.sha256(png).hexdigest(), preview_alpha='opaque_for_RGB_inspection',
                    appearance_2026_verified=False, home_away_verified=False, installed=False)
                records.append(record)
                figures.append(f'<figure><a href="{filename}"><img loading="lazy" src="{filename}" alt="{html.escape(name)} {slot["slot"]}"></a><figcaption>{slot["slot"]} · origem {info["width"]}×{info["height"]} · prévia {w}×{h}</figcaption></figure>')
            except (fc.DecodeError, ValueError, OSError) as exc:
                errors.append(dict(club=name,slot=slot['slot'],error=str(exc)))
                figures.append('<p>Falha: '+html.escape(str(exc))+'</p>')
        warning = 'Ordem do kitpack difere de p1/p2: '+', '.join(club['default_order'][:3]) if club['order_differs'] else 'Camisa 1/2 e temporada ainda precisam de conferência.'
        cards.append(f'<section data-name="{html.escape(name.lower())}" data-division="{club["division"]}"><h2>{html.escape(name)} <small>Série {club["division"]}</small></h2><p>{html.escape(warning)}</p><div class="pair">'+''.join(figures)+'</div></section>')
    page = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Conferência dos uniformes A/B</title>
<style>body{font:16px system-ui;background:#15191e;color:#eee;margin:24px auto;max-width:1200px;padding:0 16px}input,select{font:inherit;padding:10px;margin:4px;border-radius:6px}section{background:#222a33;padding:20px;margin:20px 0;border-radius:12px}.pair{display:flex;gap:16px}figure{flex:1;margin:0;min-width:0}img{width:100%;height:auto}small,figcaption{color:#bdcbd8}h2{margin:0}p{line-height:1.5}@media(max-width:700px){.pair{display:block}figure{margin-top:16px}}</style>
<h1>Conferência dos uniformes A/B</h1><p>40 clubes · slots p1 e p2, mais as alternativas indicadas na ordem de Botafogo e Fluminense. Prévia do atlas de textura, não do uniforme vestido. Nada instalado no jogo. Temporada, patrocinadores e função titular/reserva ainda precisam de conferência. Alpha ignorado somente nesta visualização RGB.</p>
<label>Clube <input id="q" placeholder="Buscar clube"></label><label>Série <select id="division"><option value="">Todas</option><option>A</option><option>B</option></select></label><p id="count" aria-live="polite"></p>'''+''.join(cards)+'''
<script>const normalize=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();function filter(){let n=0;for(const s of document.querySelectorAll('section')){s.hidden=!normalize(s.dataset.name).includes(normalize(document.querySelector('#q').value))||(document.querySelector('#division').value!==''&&s.dataset.division!==document.querySelector('#division').value);if(!s.hidden)n++}document.querySelector('#count').textContent=n+' clubes exibidos'}document.querySelector('#q').addEventListener('input',filter);document.querySelector('#division').addEventListener('change',filter);filter();</script></html>'''
    (output / 'index.html').write_text(page)
    (output / 'manifest.json').write_text(json.dumps(dict(previews=records,errors=errors,installed=False),ensure_ascii=False,indent=2)+'\n')
    print(f'{len(records)} previews; {len(errors)} errors; {output / "index.html"}')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
