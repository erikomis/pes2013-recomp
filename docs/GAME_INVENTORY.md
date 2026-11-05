# GAME_INVENTORY.md — Inventário do jogo (Fase 0)

> Preenchido a partir dos arquivos reais da cópia local. Nada aqui foi presumido.
> A primeira seção descreve o alvo atual. O resto é o inventário de 2026-11-03, feito no disco
> europeu BLES01746, que já não está na máquina; guardado como histórico.

## Alvo atual: BLUS31029, atualização 01.04

| Item | Valor |
|---|---|
| Disco | `~/Downloads/PES 2013 - Pro Evolution Soccer (USA) (EnFrEsPt)/`, ISO de 8.332.443.648 bytes |
| Title ID / versão do disco | `BLUS31029` / 01.00 |
| EBOOT 1.00 decifrado | SHA-256 `8c329ec4…`, idêntico byte a byte ao do disco europeu |
| Atualização | `UP0101-BLUS31029_00-PES2013USPATCH04-A0104-V0100-PE.pkg`, versão 01.04 |
| `game/EBOOT.BIN` (SELF do PKG) | 11.849.536 bytes · SHA-256 `38b0fdab…` · NPDRM rev `0x0019`, licença livre, sem `.rap` |
| `game/EBOOT.elf` | 28.788.720 bytes · SHA-256 `7cc8f4aa…` |
| entry (OPD) / TOC | `0x1A95538` / `0x1ADE880` |
| Funções únicas / OPD | 23.462 / 33.399 |
| Funções convertidas | 66.772, em 13 arquivos de `recompiled/BLUS31029/` |
| Imports de firmware | 375 em 27 bibliotecas |
| Data Pack 6 | `BLUS31029_DOWNLOAD/USRDIR`: `dt0f.img`, `dt0f_6.img`, `pes13pv.sfd` |
| Option File | `SAVEDATA/`, 1.106 saves; só `BLUS31029EEDIT/DATA.BIN` vem cifrado pelo PS3 |

Imagens SPU (9, mesmos tamanhos da tabela histórica abaixo), por offset no ELF: `0x019F0600`,
`0x019F6800`, `0x01A06280`, `0x01A06E00`, `0x01A07A80`, `0x01A08E80`, `0x01A0A580`, `0x01A2BE80`,
`0x01A4F600`. Jobs SPURS, por endereço: `0x01A0F380` (22.944 B, curvas de animação) e `0x01A14D80`
(5.312 B, por quadro), com os mesmos bytes do 1.00.

# Histórico: disco europeu BLES01746, 1.00

## Fonte

| Item | Valor |
|---|---|
| Disco fornecido | `~/Downloads/PES 2013 - Pro Evolution Soccer (Europe) (EsPt)/PES 2013 - Pro Evolution Soccer (Europe) (Es,Pt).iso` |
| Tamanho da ISO | 7.304.445.952 bytes |
| Conteúdo do disco | `PS3_DISC.SFB`, `PS3_GAME/` (ICON0, PIC1, PARAM.SFO, LICDIR/LIC.DAT, TROPDIR/NPWR03692_00, USRDIR/), `PS3_UPDATE/` (vazio) |
| Procedência do rip | iso com marcas de site de roms; o `EBOOT.BIN` veio com o SELF.header intacto e conteúdo decifrado — nossa descriptografia partiu dele e produziu um ELF válido (ver abaixo) |
| Link no projeto | `../game_iso` (symlink para a pasta em Downloads) |

## Identificação

| Item | Valor |
|---|---|
| **Title ID** | **BLES01746** (região Europa — edições Es/Pt, BLES) |
| Título (PARAM.SFO) | `Pro Evolution Soccer 2013` |
| APP_VER / VERSION | 01.00 / 01.00 |
| PS3_SYSTEM_VER | 04.2100 |
| NP_COMMUNICATION_ID (trophies) | NPWR03692_00 |
| SFB | HYBRID_FLAG, TITLE_ID BLES-01746 |

## EBOOT

| Item | Valor |
|---|---|
| `EBOOT.BIN` (SELF, original) | 11.678.408 bytes · SHA-256 `c7d5bb0e23c551eee9099089c442ebd8cee59beabca20d0d6cb9d9b349866a27` |
| SELF header | v2 · key_rev `0x001C` · type APP · auth_id `0x1010000001000003` · version 1.0000 |
| `EBOOT.elf` (decifrado localmente com as chaves públicas do RPCS3, via `decrypt_self.py` do porte de Deadpool) | 28.389.608 bytes · SHA-256 `8c329ec412fa16ad3957ddee654118a2dfd3c6fa17b717272b14f8a143a703e7` |

## Imagem PPU (ppu_loader, toolkit r8)

| Item | Valor |
|---|---|
| entry (OPD) | `0x1A354E8` → código `0x1A354E8` |
| TOC do módulo (r2) | `0x1A7DE98` |
| Região OPD | `0x1A35478`, tamanho `0x40A20`, 33.092 descritores |
| Funções únicas | **23.255** |
| Segmentos de carga | `vaddr 0x10000 filesz/memsz 0x1A13008` (R-X); `vaddr 0x1A30000 filesz 0xEC90C memsz 0x2805E0 bss 0x193CD4` (RW-) |
| JSONs gerados | `analysis/BLES01746/EBOOT.{functions,image,loader,imports}.json` |

### Imports de firmware — 381 funções em 28 bibliotecas

| Biblioteca | Funções | Observação |
|---|---|---|
| sysPrxForUser | 43 | runtime base (lwmutex, threads do forge) |
| cellSpurs | 40 | **SPURS pesado** — tarefas SPU no coração do jogo |
| cellSysutil | 32 | menus do sistema, save-data dialogs |
| sceNp | 27 | rede (só para modos online; o faul gira offline) |
| sys_net | 25 | BSD sockets |
| cellHttp | 22 | |
| cellGcmSys | 20 | **RSX** — pipeline gráfico |
| sceNpCommerce2 | 20 | loja/PSN; offline o passa认证 correto |
| sys_fs | 19 | arquivos |
| sys_io | 17 | **input** (cellPad etc.) |
| cellSsl | 14 | |
| cellAudio | 12 | áudio |
| sceNpTrophy | 11 | trophies |
| cellCamera / cellMic | 11+8 | voice chat |
| cellSearchUtility, cellMusicUtility, cellNetCtl, sceNpSns, cellSysmodule, cellSync, cellPhotoDecodeUtil, cellJpgDec (7), cellGame (8), cellRtc (7), cellHttpUtil (1), cellSysutilAvconfExt (1), cellPhotoImportUtil (1) | 3–9 | demais |

**Ponto de atenção:** nenhum import de `cellVdec`/`cellAdec`/`libmixer`/`cellPamf` visível no estático — os vídeos de intro/replay do PES devem vir por PRX carregado em runtime, por decodificador dentro das imagens SPU, ou pelo formato próprio Konami. Verificar na Fase 1 com logs de `cellSysmodule`. (JpgDec presente para o loading.)

## SPU (extract_spu_images)

**9 imagens embutidas no EBOOT**, 496.660 bytes no total, extraídas em `analysis/BLES01746/spu/`:

| # | Offset no ELF | Tamanho | Arquivo |
|---|---|---|---|
| 0 | 0x01992A80 | 24.964 B | spu_0000_at_01992A80.elf |
| 1 | 0x01998C80 | 35.700 B | spu_0001_at_01998C80.elf |
| 2 | 0x019A8700 | 2.900 B | spu_0002_at_019A8700.elf |
| 3 | 0x019A9280 | 3.156 B | spu_0003_at_019A9280.elf |
| 4 | 0x019A9F00 | 5.076 B | spu_0004_at_019A9F00.elf |
| 5 | 0x019AB300 | 5.844 B | spu_0005_at_019AB300.elf |
| 6 | 0x019ACA00 | 137.396 B | spu_0006_at_019ACA00.elf |
| 7 | 0x019CE300 | 145.204 B | spu_0007_at_019CE300.elf |
| 8 | 0x019F1A80 | 136.420 B | spu_0008_at_019F1A80.elf |

(os 3 grandes são quase certamente decodificador de H.264/áudio e/ou física de quan; confirmar na Fase 1)

## Dados do disco (USRDIR)

Pacotes de dados com par `dtNN.img` + `dtNN.crc` (CRC de verificação de 4 bytes) e variantes `_q`/`_s`:

- `dt00_q.img` 420,4 MB · `dt00_s.img` 522,4 MB (streams)
- `dt01.img` 784,9 MB (o maior — provavelmente estádios/replays/modelos)
- `dt02–dt0e.img` de 2,1 a 995,5 MB, com variantes `_q`/`_s` para dt00 e dt05; `_s` = streaming? `_q` = qualidade? **A confirmar** comparando com a estrutura de PC (Fase 4) e com logs de `sys_fs` (Fase 1).
- Contagem exata e checksums: F1 pendente (ISO foi desmontada após a cópia dos args; remontar para varrer).

## Ambiente de toolkit

| Item | Valor |
|---|---|
| Toolkit | `~/Desktop/ps3recomp-up-r8` (fork erikomis/ps3recomp @ r8 — requerido pelo molde Deadpool) |
| Python | venv do Deadpool `deadpool-recomp/tools/.venv` (3.12.16) — o sistema está no 3.14, o r8 no 3.12 |
| Referência de porta irmã | `deadpool-recomp` (`NPUB31069`), `recomp-infamous-2`, `resistance2-recomp` |
