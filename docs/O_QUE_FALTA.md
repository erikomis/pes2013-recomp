# O que falta — PES 2013 no macOS

Situação em 04/11/2026, tarde. Versão: disco americano BLUS31029, atualização 01.04. Lista de trabalho na ordem em que os problemas
aparecem. Os detalhes técnicos de cada subsistema ficam em `COMPATIBILITY.md`.

**Como rodar:** `tools/run.sh > cache/boot-meu.log 2>&1` na raiz do projeto.
Fecha com `Ctrl+C`.

## Onde o jogo está hoje

| Etapa | Estado |
|---|---|
| Logos, título, menus em português | Funcionam |
| Seleção de times, escalações, hino | Funcionam: uniformes e rostos corretos, de perto |
| Partida | Roda, com placar, relógio e minimapa, e não fecha |
| Jogadores na câmera de jogo | Corrigidos em uma partida sem janela; falta confirmar em janela |
| Data Pack 6 e Option File | Instalados e carregados pelo jogo |
| Controle físico, som, partida completa | A verificar |

## 1. Prioridade atual

- [ ] **Confirmar os jogadores em janela:** sem janela, a partida não teve nenhuma textura
      vazia. Falta confirmar na janela, com o executável final.
- [ ] **Desempenho em janela:** sem janela, a partida faz 60 a 66 fps no jogo e cerca de 30 fps em
      trechos como replays, usando cerca de 280% de CPU (antes, cerca de 18 fps e 414%). Falta medir
      em janela e verificar travadinhas. A captura `PS3RECOMP_METAL_FRAME_DUMP` tem custo: deixe
      de usar quando não precisar dela.
- [ ] **Teclado virtual sem tela:** o nome do perfil é aceito automaticamente.

### Resolvido nesta rodada (sem commit)

- **Desempenho:** nada era otimizado, porque `CMAKE_BUILD_TYPE` está vazio. Agora o runtime e a cola
  usam `-O2`, e o código convertido usa `-O1` (`port/CMakeLists.txt`). O log verboso também saiu do
  padrão (`PS3_VERBOSE=0` em `tools/run.sh`; passe `PS3_VERBOSE=1` para depurar). Uma compilação
  completa leva cerca de 20 minutos e o executável caiu de 649 MB para 414 MB.
- **Jogadores invisíveis e árbitro preto na câmera de jogo:** eram dois defeitos no motor de
  desenho (`rsx_draw_engine.c`). O jogo reduz cada uniforme para um alvo na memória principal, e
  essa imagem ficava só na GPU. Além disso, a tabela de 64 superfícies enchia antes da partida e
  os alvos seguintes eram descartados em silêncio. O limite agora é 512, com aviso no log.
- **Pele neon e rostos pretos:** o `NV308A` (`cellGcmSys.c`) aceitava 256 das 1792 palavras
  de cada envio, e todo fragment program perdia o que vinha depois de 1 KB. Na memória,
  2.389 de 2.653 programas tinham esse buraco; depois da correção, 0 de 298.
- **Uniforme em faixas (o "arco-íris"):** textura linear com mipmaps perdia o pitch nos
  níveis menores (`rsx_texture_layout.c`).
- **Pose T:** `JOBLIST` não implementado (`cellSpurs.c`), então a animação nunca rodava.
- **Lentidão no carregamento:** jobs convertidos em nativo (`tools/lift_jobs.sh`).

### Como reproduzir sem teclado

`PAD_FILE=<arquivo>` aceita botões escritos no arquivo; com `PS3RECOMP_METAL_HEADLESS=1`
e `PS3RECOMP_METAL_FRAME_DUMP`, dá para navegar até a partida olhando os frames. Sequência
a partir do título: START, START, CROSS (7 vezes), CROSS (pontapé de saída).
Use `PS3_GAMEDATA_ROOT` e `PS3_HDD1_ROOT` próprios.

### Carregamento travado (resolvido, sem commit)

O job SPURS em `0x019B7200` (`JOBCRT Ver14`) não tem imagem liftada e roda no
interpretador. Havia dois defeitos em `../ps3recomp-up-r8/runtime/spu/spurs_job.c`:

1. Com `image_id` 0, o coringa do registro, o interpretador saltava para a função
   `0xE0` de outra imagem. Agora um job sem imagem usa -1.
2. O job era carregado em LS 0, onde a simulação do kernel zerava `0x1C0`. Para o
   interpretador, zero é `stop`, então o job parava antes de fazer qualquer trabalho
   e o jogo esperava o event flag para sempre. Agora ele carrega em `0x3000`.

### Tela de nível (resolvido, sem commit)

Ao confirmar, o jogo abre o teclado virtual para criar os "Dados pessoais". O HLE
exigia um `cellOskDialogInit` que o jogo não importa, respondia `NOT_INITIALIZED` e
não enviava os eventos `0x502`, `0x503` e `0x504`, então o jogo voltava à página.
Correção em `../ps3recomp-up-r8/libs/misc/cellOskDialog.c`.

### Fechamento no Enter (resolvido, sem commit)

O Enter fazia o jogo procurar saves, e ele abortava no meio dessa busca. Toda chamada
HLE pode entregar um vblank pendente; esse callback recomeçava no topo da pilha de
callbacks e sobrescrevia o callback que ainda rodava. A string do jogo ficava com um
ponteiro inválido, o `free` recebia `EINVAL` e o jogo chamava `abort()`.

A correção está em `ppu_guest_call` e `ppu_guest_call_ct`
(`../ps3recomp-up-r8/runtime/ppu/ppu_loader.cpp`): uma chamada aninhada agora começa
abaixo do SP atual.

Teste sem teclado (cerca de 1 minuto):

    tools/run.sh PS3RECOMP_METAL_HEADLESS=1 PAD_SCRIPT=35:0x4000 > cache/teste.log 2>&1

Antes da correção o jogo abortou em todas as execuções medidas. Depois, ficou aberto
nas duas execuções feitas (121 s e 151 s, encerradas por mim). Ainda não foi testado
com janela e teclado de verdade.

## 2. Para o menu ficar utilizável

- [ ] **Vídeos `.sfd`:** o fundo do menu usa `pes_topBG_*.sfd`. As tarefas de vídeo
      ficam em `WAIT_SIGNAL`; não está provado que decodifiquem.
- [ ] **Controle:** o teclado funciona no menu; um controle físico não foi testado.
- [ ] **Funções sem implementação:** `0x05C65656` (37 chamadas, biblioteca
      desconhecida), `inet_addr`, `sceNpSns` e `cellSysutilAvconfExt`. Até agora
      parecem inofensivas.

## 3. Para jogar uma partida (M2 a M5)

- [ ] **Gráficos 3D:** a partida renderiza estádio cheio, os dois times, goleiros, árbitro e
      bandeirinhas. Falta avaliar a qualidade em janela e ao longo de uma partida inteira.
- [x] **Métodos RSX desconhecidos:** o log agora lista **um por método distinto**.
      A tabela tinha 4096 posições e descartava em silêncio todo método `>= 0x1000`
      (0x1D78, 0x1EA4, ...); corrigida para o espaço inteiro (`0x1FFC`). No log atual
      são 22 métodos distintos, todos de valor `0`/`0xFEED0000` (registradores), nenhum
      de geometria. Já está no executável atual.
- [ ] **Som:** o mixer do jogo produz áudio correto, mas o CoreAudio deste Mac falhou ao abrir o
      dispositivo (`-66681`), também no `afplay`. Reiniciar com `sudo killall coreaudiod` e
      testar. A narração não foi testada.
- [ ] **Saves:** salvar e carregar não foi validado. A Master League e o Rumo ao
      Estrelato dependem disso. As opções são gravadas em
      `rpcs3/dev_hdd0/home/00000001/savedata` e foram lidas de volta em um boot seguinte.
      Saves de jogo ainda não foram testados.
- [ ] **Rede e troféus:** devem funcionar offline, sem travar. Não testado.
- [ ] **Partida completa:** seleção de times → carregamento → partida → intervalo
      → fim.

## 4. Depois de jogável (M6 a M9)

Nada iniciado:

- [ ] M6: texturas HD
- [ ] M7: elencos e uniformes Brasil 2026 — preparação iniciada: 40 clubes e
      2.050 registros CBF coletados, leitor de elencos do save implementado;
      atualização ainda não aplicada. Ver `BRAZIL_2026_DATA.md`.
- [ ] M8: presets de desempenho (a otimização de compilação já foi feita)
- [ ] M9: launcher e distribuição sem dados do jogo

## 5. Organização

- [ ] **Commits pendentes:** as correções estão sem commit em `../ps3recomp-up-r8`,
      junto com diagnósticos desligados por padrão. Fazer commit só quando o dono pedir.
- [x] **`COMPATIBILITY.md`:** linha do 3D e status do M1 corrigidos (M1 ✅, M2 parcial).
- [x] **Logs:** os dois maiores (`boot-24.log` 2,9 GB e `boot-27.log` 1,7 GB) apagados;
      `cache/` caiu de 6,0 GB para 1,4 GB.
- [x] **Arquivo solto:** o `1` na raiz era um frame PPM de 20:32 e foi removido.

## Já resolvido

- Fechamento ao apertar Enter na tela de título (sem commit).
- Tela de nível que voltava sem avançar (sem commit).
- Travamento no carregamento depois da configuração (sem commit).
- Tela preta e travamento do DMA (`stop 0x110`).
- Falha do `buffer.tmp` (`PS3_HDD1_ROOT` no `tools/run.sh`).
- `sys_prx_register_library`, `sys_mempool_create` e `sys_mempool_get_count`.

## Versão instalada (2026-11-04)

Disco americano BLUS31029, atualização 01.04, Data Pack 6 e Option File Brasileirão.
Testado sem janela, em pastas separadas: chega ao menu e a uma partida, sem abort, com o
Option File carregado (`EEDIT`, emblemas e uniformes). A abertura com o assistente em
Português do Brasil foi até o carregamento do `EEDIT`.

- **Sem save de opções:** a primeira abertura repete o assistente; escolha Português do Brasil.
- **Não testado:** em janela, com teclado.

## Copas e visuais — atualização de 05/11/2026

- [x] Identificar os 203 clubes das três copas (126 Copa do Brasil / 47 Libertadores / 56 Sul-Americana, com sobreposição).
- [x] Conferir 126 identidades CBF por nome e UF; coletar registros dos 89 brasileiros adicionais e referências dos 77 estrangeiros.
- [x] Coletar 210 partidas nacionais para referências de escalação; gerar rascunhos de até 32 candidatos com evidência.
- [ ] Completar elencos profissionais atuais: só 6 dos 89 clubes adicionais têm ao menos 18 candidatos confirmados pelo cruzamento conservador; buscar estaduais/regionais e páginas oficiais atuais.
- [ ] Resolver a falta de lista de atletas do jogo CBF 834781; conferir posições, transferências, lesões e novos contratados.
- [x] Baixar e inspecionar 13 arquivos adicionais de faces da coleção River Plate (26 BINs).
- [ ] Validar identidades/aparência, adaptar faces PC para PS3 e associar IDs sem conflito.
- [ ] Baixar uniformes 1/2 corretos de 2026 para clubes adicionais; kit Rivadavia encontrado é antigo e foi excluído da cobertura atual.
- [ ] Implementar/mapeiar as competições e validar uma partida completa; nenhum patch dessas copas foi instalado.

Detalhes e listas: [COMPETICOES_2026.md](COMPETICOES_2026.md).
