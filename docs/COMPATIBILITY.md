# COMPATIBILITY.md — status por subsistema (Fase 0 → contínuo)

Legenda: `não testado` · `falha` · `parcial` · `funcional`

| Subsistema | Status | Notas |
|---|---|---|
| Descriptografia EBOOT (1.04, NPDRM rev 0x19, licença livre) | **funcional** | ELF válido, 23.462 funções; via `decrypt_self.py`, sem `.rap` |
| ppu_loader / lifter | **funcional** | 66.772 funções liftadas em `recompiled/BLUS31029/` (13 TUs) |
| spu lift (9 imagens) | **funcional** | 9 imagens liftadas em `port/spu/`; `stop 0x110` implementado (receive_event) |
| cellGcmSys / RSX → Metal | **funcional** | Frame dumps da surface RSX confirmam 3D + 2D corretos: title screen completo (estádio, torcida, jogadores, arte "PES Full Control"), wizard, vídeo de fundo do menu, menu de treino e o exercício de treino em 3D (campo, bola, torcida, placas, minimapa). Formatos de textura efetivamente usados: `0x85` A8R8G8B8, `0x86` DXT1, `0x87` DXT23, `0x88` DXT45, `0x81` B8, `0x9A` W16Z16Y16X16F — todos com decodificador. O "32 draws" que aparecia nos logs é só o teto de log em `rsx_commands.c` (`PS3_LOG_FIRST(_d, 32)`), não uma contagem. Defeitos fechados: os kits em listras (mip linear recebia largura própria), o buraco nos fragment programs no local memory (`NV308A COLOR` parava em 0x07FC em vez de 0x1FFC) e o árbitro/bandeirinha preto em T-pose — esse último sumiu junto com o `JOBLIST`; o hino mostra árbitros e bandeirinhas com uniforme, rosto e pose animada. Também fechado: os jogadores invisíveis na câmera de jogo (ver notas de campo). Uma partida sem janela teve 0 texturas 128x128 vazias, com os dois times, goleiros, árbitro e bandeirinhas na câmera de jogo e no replay |
| cellSpurs (40 imports) | parcial | tasksets/tasks iniciam e recebem eventos; tarefas de vídeo ficam em WAIT_SIGNAL. Os **dois jobs do EBOOT estão liftados e registrados** (`port/spu/job_88F100FF85C987D1/` = `jobmod_pes00`, 22944 B, ids 10; `job_4A91FDAB209A2A8B/` = `job_pes01`, 5312 B, id 11): no log saem `dispatch HIT fp=… image=10/11` e `RETURNED rc=0`, com **0 `dispatch MISS` e 0 `interp bin`**. O `JOBLIST` do `jc_execute` (que era ignorado: "nested arrays TODO") foi implementado e agora despacha `n=15`/`n=9` jobs por chain. Consequência visível: as poses do hino/escalação animam (antes T-pose). |
| cellAudio | **funcional** | Estalos na partida corrigidos em 08/11/2026: o mixer mandava blocos conforme o CoreAudio liberava espaço, em lotes, e acordava o mixer do jogo várias vezes de uma vez; sob carga (partida) o jogo escrevia blocos fora de ordem, com um salto em quase toda emenda de bloco (milhares por minuto na gravação `AUDIO_WAV`; nos menus, nenhum). Agora cada bloco sai a cada 5,33 ms pelo relógio, como no console, e a fila do dispositivo fica quase cheia como margem (blocos 4 ms adiantados enquanto ela enche, nunca juntos). Mesma partida gravada antes e depois: de 200-500 saltos a cada 10 s para 4 saltos em 6 min, 0 falhas de fila. `PS3_AUDIO_ROOM_PACE=1` volta ao ritmo antigo. O CoreAudio às vezes não abre a saída (`-66681`), em qualquer app do Mac; aí o mixer segue só o relógio |
| sys_io / input (SDL2 no macOS) | parcial | 17 imports; o dono joga pelo teclado; controle físico não testado |
| sys_fs (dt*.img) | **funcional** | dt06/dt0f/pes*.sfd lidos; VFS + `PS3_HDD1_ROOT` (cache) no `tools/run.sh` |
| cellSaveData (saves) | **funcional** | Causa raiz do `abort()`: a `std::string` do callback `funcFixed` (0x01148E20) era sobrescrita por um callback aninhado no mesmo thread (todo HLE chamado de dentro do convidado bombeia vblank → `ppu_guest_call` reiniciava no topo do scratch stack). Corrigido com `ppu_guest_call_sp()` (pilha por profundidade/thread); 180 s e 320 s sem `abort()`, `funcFixed` devolve `-4` e o save das opções completa (`SAVE complete for 'BLES01708EOPTION'`). Correção ainda não commitada |
| sceNp*/rede | não testado (dev offline) | 96 imports; tudo deve rodar OFFLINE |
| cellSysutil (menus, diálogos) | **funcional** | callbacks, diálogos, `SysCacheMount` e idioma funcionam; cache grava em `rpcs3/dev_hdd1`. Idioma: o host reporta `PORTUGUESE_BR` (17) e o jogo escreve em espanhol; `PS3_LANG=PT` (7) dá os rótulos em português e o `tools/run.sh` agora usa isso por padrão. A página 1 do wizard **sempre abre em "Español"** (o sistema não define a seleção): DOWN + CROSS uma vez escolhe "Português", e é essa escolha que o save guarda |
| Áudio de narração Es/Pt | não testado | depende dos pacotes do disco |
| Trophies (sceNpTrophy) | não testado | deve ser NO-OP offline |

## Marcos (do plano mestre)

| Marco | Teste mínimo | Status |
|---|---|---|
| M0 Inventário | executáveis, Title ID, módulos | ✅ (este doc) |
| M1 Boot | logos → menu sem crash | funcional na execução do dono: logos, título, configuração e menus em português até entrar em uma partida |
| M2 Partida | partida completa | parcial: chega ao jogo com bola rolando, intervalo e fim não testados; a câmera de jogo está correta em uma partida sem janela, falta confirmar em janela |
| M3 Gráficos | render sem corrupção | parcial: sem defeito conhecido nas capturas; falta avaliar em janela |
| M4 Áudio/input | narração + controle | não iniciado |
| M5 Saves | salvar/carregar | não iniciado |
| M6 Texturas HD | 3 substituições-piloto | preparação: filtro 16× configurado; exportação/importação de overlays de uniforme validada byte a byte; nenhum pacote HD ativo. Ver `VISUAL_2026.md` |
| M7 Brasil 2026 | elencos/kits | preparação: dados dos 40 clubes coletados e leitor de elencos implementado; nada aplicado ao save. Ver `BRAZIL_2026_DATA.md` |
| M8 Otimização | preset equilibrado | parcial: compilação otimizada; sem janela, 60 a 66 fps no jogo; presets não iniciados |
| M9 Release | distribuição limpa | não iniciado |

## Notas de campo

- **Versão.** Desde 2026-11-04 o alvo é o disco americano `BLUS31029` com a atualização
  01.04, o Data Pack 6 e o Option File Brasileirão. O EBOOT 1.00 americano é idêntico byte
  a byte ao do disco europeu `BLES01746`; o 1.04 é outro ELF (conversão refeita). Diretórios
  de save e cache usam o prefixo `BLUS31029`; os dados anteriores em `BLES...` foram apagados.
- **Option File.** `tools/install_savedata.py` instala `SAVEDATA/` em `rpcs3/`. Só o
  `DATA.BIN` de `BLUS31029EEDIT` vem cifrado pelo PS3. As chaves ficam fora do repositório.
- **Jogadores distantes: corrigido (sem commit).** O jogo reduz cada uniforme para um alvo na memória
  principal. A imagem ficava só na GPU, e a tabela de superfícies do motor (64) enchia antes da
  partida, descartando os desenhos em silêncio. Agora os alvos vão para a memória e o limite é 512.
  Em uma partida sem janela: nenhuma textura vazia. Falta confirmar em janela.
- **Desempenho.** Medido com o mesmo roteiro, sem janela e com captura a cada 30 quadros. Média no
  trecho da partida, que mistura jogo, replays e cenas, e varia com o roteiro:

  | Etapa | fps | CPU | Linhas de log |
  |---|---|---|---|
  | Sem otimização (outro jogo aberto ao mesmo tempo) | 18 | 414% | 892 mil |
  | `-O2` no runtime, log silencioso (idem) | 47 | 412% | 168 mil |
  | Também `-O1` no código convertido, máquina livre | 39 | 283% | 168 mil |
  | Também sem as mensagens por quadro | 49 | 278% | 23 mil |

  No jogo em si, a última etapa fica em 60 a 66 fps. As duas primeiras linhas não são comparáveis
  diretamente com as duas últimas, e a diferença entre as duas últimas é do roteiro.
- **Diagnóstico de memória do jogo.** `PS3_MEMDBG=1` loga todo `sys_memory_free`
  que o runtime recusa (com o intervalo do heap do malloc do jogo) e
  `PS3_MEMDBG=2` também despeja 0x220 bytes da pilha do convidado no ponto da
  falha — foi isso que localizou o objeto `std::string` corrompido.
