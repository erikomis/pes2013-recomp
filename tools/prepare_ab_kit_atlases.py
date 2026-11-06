#!/usr/bin/env python3
"""Prepare all A/B p1/p2 UV probes, sequentially and resumably; never install."""
import hashlib
import html
import json
from pathlib import Path

import ftex_convert as fc
from probe_kit_uv import rasterize


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / 'analysis/visual-2026'
    inventory = json.loads((base / 'coverage/kit_slots.json').read_text())
    map_bytes = (base / 'kit-uv-map/pes2013-1024x512.json').read_bytes()
    mapping = json.loads(map_bytes)['data']
    w, h = mapping['target_size']
    output = base / 'ab-kit-atlases'
    output.mkdir(exist_ok=True)
    version = sha(Path(__file__).read_bytes() + (root / 'tools/probe_kit_uv.py').read_bytes()
                  + (root / 'tools/ftex_convert.py').read_bytes())
    records, errors, cards = [], [], []
    for i, club in enumerate(inventory['clubs']):
        figures = []
        for slot in club['slots']:
            if slot['slot'] not in ('p1', 'p2'):
                continue
            stem = f"club-{i:02d}-{slot['slot']}"
            png_path, record_path = output / (stem+'.png'), output / (stem+'.json')
            try:
                source = root / slot['texture']
                raw = source.read_bytes()
                if sha(raw) != slot['sha256']:
                    raise ValueError('Source hash changed since inventory')
                record = json.loads(record_path.read_text()) if record_path.exists() else {}
                reuse = (record.get('source_sha256') == sha(raw)
                         and record.get('map_sha256') == sha(map_bytes)
                         and record.get('tool_sha256') == version and png_path.exists()
                         and record.get('png_sha256') == sha(png_path.read_bytes()))
                if not reuse:
                    info = fc.read_ftex(source)
                    info['data'] = raw
                    pixels, sw, sh = fc.decode_frame_rgba(info, 0)
                    if [sw, sh] != mapping['source_size']:
                        raise ValueError('Source dimensions differ from map')
                    result, stats = rasterize(pixels, sw, sh, mapping['triangle_pairs'], w, h, True)
                    png = fc.encode_png_rgba(result, w, h)
                    png_path.write_bytes(png)
                    record = dict(club=club['club'], division=club['division'], slot=slot['slot'],
                        source=slot['texture'], source_sha256=sha(raw), map_sha256=sha(map_bytes),
                        tool_sha256=version, png=png_path.name, png_sha256=sha(png),
                        width=w, height=h, orientation='bottom_left', sampling='nearest_probe_only',
                        alpha='preserved', **stats, installed=False, ps3_verified=False,
                        season_verified=False, home_away_verified=False)
                    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
                records.append(record)
                figures.append(f'<figure><a href="{stem}.png"><img loading="lazy" src="{stem}.png" '
                               f'alt="{html.escape(club["club"])} {slot["slot"]}"></a>'
                               f'<figcaption>{slot["slot"]} · {w}×{h}</figcaption></figure>')
            except (ValueError, OSError, fc.DecodeError) as exc:
                errors.append(dict(club=club['club'], slot=slot['slot'], error=str(exc)))
        cards.append(f'<section><h2>{html.escape(club["club"])} · {club["division"]}</h2>'
                     + ''.join(figures) + '</section>')
        print(f'{i+1}/{len(inventory["clubs"])} {club["club"]}: {len(records)} atlases, {len(errors)} errors', flush=True)
        (output / 'manifest.json').write_text(json.dumps(dict(atlases=records, errors=errors,
            complete=i+1 == len(inventory['clubs']), installed=False), ensure_ascii=False, indent=2)+'\n')
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width"><title>Atlas experimentais A/B</title><style>'
        'body{background:#19212a;color:#eee;font:16px system-ui;max-width:1200px;margin:24px auto;padding:16px}'
        'figure{margin:12px 0}img{width:100%;max-width:1024px}section{border-bottom:1px solid #777;padding:16px}'
        '</style><h1>Atlas experimentais A/B</h1><p>Conversão de coordenadas PES21 → PES13. '
        'Não instalado nem validado em modelo 3D. Slots p1/p2 não confirmam titular/reserva ou temporada. '
        'Faltam acabamento das costuras, gola/braçadeira e associação às texturas reais do jogo.</p>'
        + ''.join(cards))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
