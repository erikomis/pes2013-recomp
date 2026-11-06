#!/usr/bin/env python3
"""Bounded texture capture using the existing isolated Flamengo test profile."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def preflight():
    binary = ROOT / 'build/BLUS31029/PES2013Recomp'
    if not binary.is_file():
        raise RuntimeError('Executável ausente.')
    # Read-only capability check; never rebuild another agent's runtime.
    with binary.open('rb') as stream:
        found = False
        tail = b''
        while chunk := stream.read(1024*1024):
            if b'PS3_MODS_DUMP\0' in tail+chunk:
                found = True
                break
            tail = chunk[-32:]
    if not found:
        raise RuntimeError('Este executável ainda não contém PS3_MODS_DUMP.')
    profile = ROOT / 'analysis/test-save-flamengo-2026'
    if not (profile / 'manifest.json').is_file():
        raise RuntimeError('Perfil separado do Flamengo ausente.')
    if not (ROOT / 'rpcs3/dev_hdd0/disc/BLUS31029/PS3_GAME').is_dir():
        raise RuntimeError('Disco/VFS indisponível; monte pelo launcher habitual.')
    if shutil.disk_usage(ROOT).free < 4*1024**3:
        raise RuntimeError('Menos de 4 GiB livres; captura cancelada.')
    result = subprocess.run(['pgrep', '-x', 'PES2013Recomp'], capture_output=True, text=True)
    if result.returncode == 0:
        raise RuntimeError('Já existe jogo/teste aberto. Aguarde ou feche sua própria partida.')
    if result.returncode != 1 or result.stderr.strip():
        raise RuntimeError('Não foi possível verificar os processos; captura cancelada.')
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        preflight()
    except RuntimeError as exc:
        print(exc)
        return 2
    if args.check:
        print('Pronto: executável com captura, VFS e perfil separado disponíveis.')
        return 0
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = ROOT / 'analysis/visual-2026/runtime-captures' / stamp
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(PES_ROOT=str(ROOT), PES_BUILD=str(ROOT / 'build/BLUS31029'),
               PES_GAME=str(ROOT / 'game'), PES_EBOOT=str(ROOT / 'game/EBOOT.elf'),
               PES_VFS_ROOT=str(ROOT / 'rpcs3/dev_hdd0/disc/BLUS31029'))
    for key in ('PS3_MODS', 'PS3_MODS_DIR', 'PAD_SCRIPT', 'PS3RECOMP_METAL_HEADLESS'):
        env.pop(key, None)
    env['PS3_MODS_DUMP'] = str(output / 'textures')
    print('Selecione Flamengo e examine as camisas 1 e 2. Captura limitada a 180 segundos/512 MiB.', flush=True)
    print('Somente o perfil separado de teste será usado. A janela fechará ao atingir o limite.', flush=True)
    started = time.monotonic()
    reason, size = 'process_exited', 0
    with (output / 'boot.log').open('wb') as log:
        proc = subprocess.Popen(['zsh', str(ROOT / 'tools/testar_flamengo_2026.command')],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            while proc.poll() is None:
                size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
                if time.monotonic()-started >= 180:
                    reason = 'time_limit'
                    break
                if size >= 512*1024**2 or shutil.disk_usage(ROOT).free < 4*1024**3:
                    reason = 'disk_limit'
                    break
                time.sleep(2)
        except KeyboardInterrupt:
            reason = 'user_interrupt'
        finally:
            if proc.poll() is None:
                # Only the process group created by this invocation is stopped.
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                except ProcessLookupError:
                    proc.wait()
    (output / 'capture.json').write_text(json.dumps(dict(pid=proc.pid, exit_code=proc.returncode,
        stop_reason=reason, elapsed_seconds=round(time.monotonic()-started, 2),
        observed_bytes=size, original_profile_used=False, replacements_enabled=False), indent=2)+'\n')
    print(f'Captura em {output}')
    return 0 if (output / 'textures/textures.txt').is_file() else 1


if __name__ == '__main__':
    raise SystemExit(main())
