# O que falta — PES 2013 no macOS

Situação em 06/11/2026 (itens alinhados com o `ROADMAP.pt-BR.md`). Versão: disco americano BLUS31029, atualização 01.04. Lista de trabalho na ordem em que os problemas
aparecem. Os detalhes técnicos de cada subsistema ficam em `COMPATIBILITY.md`.

**Como rodar:** `tools/run.sh > cache/boot-meu.log 2>&1` na raiz do projeto.
Fecha com `Ctrl+C`.

## Onde o jogo está hoje

| Etapa | Estado |
|---|---|
| Logos, título, menus em português | Funcionam |
| Seleção de times, escalações, hino | Funcionam: uniformes e rostos corretos, de perto |
| Partida | Roda, com placar, relógio e minimapa, e não fecha |
| Jogadores na câmera de jogo | Funcionam: um amistoso foi jogado até o fim em janela |
| Data Pack 6 e Option File | Instalados e carregados pelo jogo |
| Teclado e DualSense (SDL) | Funcionam |
| Som | Funciona na partida; o início do replay ainda perde alguns blocos |
| Partida completa | Funciona: amistoso jogado até o fim em janela |
| Fechar o jogo | Fechar a janela, Cmd-Q ou SIGTERM encerram o processo (SIGTERM testado; o botão de fechar ainda não visto) |
| Perfil Brasil 2026 | Séries A e B com 20 clubes, Libertadores e Sul-Americana, uniformes 1 e 2 e 63 rostos HD; visto sem janela e no seletor de times |

## 1. Prioridade atual

- [x] **Confirmar os jogadores em janela:** um amistoso foi jogado até o fim em janela.
- [x] **Saída limpa:** fechar a janela, Cmd-Q ou SIGTERM encerram o processo, depois de um
      save em andamento. Antes ele continuava rodando sem janela.
- [ ] **Resolução interna (`PS3_RES_SCALE`):** está na build (1080p, 1440p, 4K); falta medir o
      fps de cada degrau com a máquina livre.
- [ ] **Desempenho em janela:** sem janela e com a máquina livre, a partida faz 60,0 fps (p95
      17,6 ms) e os replays 30,0 fps, com cerca de 133% de CPU (antes, cerca de 18 fps e 414%).
      Falta medir em janela, com a build final, e verificar travadinhas. A captura
      `PS3RECOMP_METAL_FRAME_DUMP` tem custo: deixe de usar quando não precisar dela.
- [ ] **Pico no início do replay:** um quadro de 112-207 ms quando começa um replay ou troca a
      cena; é onde estão os buracos de áudio que sobraram. Não é compilação de shader.
- [ ] **Teclado virtual sem tela:** o nome do perfil é aceito automaticamente.

### Resolvido nesta rodada (as mudanças do toolkit estão em `patches/`)

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

### Carregamento travado (resolvido)

O job SPURS em `0x019B7200` (`JOBCRT Ver14`) não tem imagem liftada e roda no
interpretador. Havia dois defeitos em `../ps3recomp-up-r8/runtime/spu/spurs_job.c`:

1. Com `image_id` 0, o coringa do registro, o interpretador saltava para a função
   `0xE0` de outra imagem. Agora um job sem imagem usa -1.
2. O job era carregado em LS 0, onde a simulação do kernel zerava `0x1C0`. Para o
   interpretador, zero é `stop`, então o job parava antes de fazer qualquer trabalho
   e o jogo esperava o event flag para sempre. Agora ele carrega em `0x3000`.

### Tela de nível (resolvido)

Ao confirmar, o jogo abre o teclado virtual para criar os "Dados pessoais". O HLE
exigia um `cellOskDialogInit` que o jogo não importa, respondia `NOT_INITIALIZED` e
não enviava os eventos `0x502`, `0x503` e `0x504`, então o jogo voltava à página.
Correção em `../ps3recomp-up-r8/libs/misc/cellOskDialog.c`.

### Fechamento no Enter (resolvido)

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
nas duas execuções feitas (121 s e 151 s, encerradas por mim). Em 05/11 foi confirmado
em janela e com teclado: um amistoso jogado até o fim.

## 2. Para o menu ficar utilizável

- [ ] **Vídeos `.sfd`:** o fundo do menu usa `pes_topBG_*.sfd`. As tarefas de vídeo
      ficam em `WAIT_SIGNAL`; não está provado que decodifiquem.
- [x] **Controle:** teclado (Enter = START, Espaço = CROSS) e DualSense pelo SDL. Falta
      mapear o esquema inteiro de controle do PES no launcher.
- [ ] **Funções sem implementação:** restam `inet_addr` (`0xDABBC2C0`) e
      `cellSysutilAvconfExt` (`0xFAA275A4`), uma chamada cada no boot; parecem inofensivas.
      Feito em 11/11/2026: `0x05C65656` era `sys_mempool_try_allocate_block` (38 chamadas na
      inicialização, todas recebiam 0); agora entrega blocos de verdade, junto com
      `sys_mempool_free_block`. Com isso o jogo passou a ligar a trilha sonora personalizada
      (`cellSearchInitialize`, `cellMusicInitialize2`), que agora responde "indisponível" em vez
      de um OK falso. Visto sem janela até uma partida, sem chamadas novas sem implementação.

## 3. Para jogar uma partida (M2 a M5)

- [x] **Gráficos 3D:** a partida renderiza estádio cheio, os dois times, goleiros, árbitro e
      bandeirinhas, em janela e ao longo de um amistoso inteiro.
- [x] **Métodos RSX desconhecidos:** o log agora lista **um por método distinto**.
      A tabela tinha 4096 posições e descartava em silêncio todo método `>= 0x1000`
      (0x1D78, 0x1EA4, ...); corrigida para o espaço inteiro (`0x1FFC`). No log atual
      são 22 métodos distintos, todos de valor `0`/`0xFEED0000` (registradores), nenhum
      de geometria. Já está no executável atual.
- [x] **Som:** o mixer do jogo roda em tempo real (48 kHz) sem buracos na partida. Resta o pico
      no início do replay (seção 1). A falha `-66681` do CoreAudio era do Mac, não do porte.
      A narração não foi testada.
- [ ] **Saves:** salvar e carregar não foi validado. A Master League e o Rumo ao
      Estrelato dependem disso. As opções são gravadas em
      `rpcs3/dev_hdd0/home/00000001/savedata` e foram lidas de volta em um boot seguinte.
      Saves de jogo ainda não foram testados.
- [ ] **Rede e troféus:** devem funcionar offline, sem travar. Não testado.
- [x] **Partida completa:** seleção de times → carregamento → partida → intervalo
      → fim. Um amistoso foi jogado até o fim em janela.

## 4. Depois de jogável (M6 a M9)

Preparação parcial; itens abaixo ainda não concluídos:

- [ ] M6: texturas HD. Feitos: gramado HD dos dois gramados vistos nas partidas
      (4096x2048, `gramado-hd`) e rostos HD de 2026 (`faces-2026`, 63 jogadores).
      Faltam os gramados dos outros estádios, a bola, a torcida e as placas.
- [ ] M7: Brasil 2026. Feito no perfil de teste (`SAVE_BRASIL_40_2026.md`):
      - [x] Séries A e B com 20 clubes cada, nomes em todos os idiomas, elencos de
            2026 dos 40 clubes (visto sem janela).
      - [x] Libertadores 2026 (38 clubes) e liga sul-americana (18 clubes da
            Sul-Americana), com elencos de 2026 e escudos.
      - [x] Uniformes 1 e 2 de 2026 dos 40 clubes como pacote de texturas (vistos no
            seletor de times).
      - [x] Nenhum jogador com o rosto de outro (14 rostos próprios, os outros fictícios).
      - [x] Posições, habilidades, pé, pé fraco, forma, altura, idade e nacionalidade
            nos 2.265 jogadores renomeados (visto em Editar > Jogadores).
      - [x] Nomes de 2026 nos 20 estádios do criador de estádios.
      - [x] Cartas do eFootball 2026: 977 aplicadas (11/11/2026, os 89 clubes pesquisados; escalações refeitas); os outros 1.288 não têm carta e usam um modelo por
            posição.
      - [x] Rostos 2026: 93 no Editar, 87 na partida (11/11/2026). Faltam 6 na partida, as 23
            faces ligadas sem chave e os 54 arquivos sem jogador de 2026.
      - [ ] Uniformes dos clubes estrangeiros: nenhuma fonte de 2026 encontrada.
      - [ ] Uma partida, a Master League e uma Libertadores jogadas com o perfil.
      - [ ] Copa do Brasil: o jogo não tem a competição nem vagas para 126 clubes; só
            uma copa personalizada com os clubes que existem.
      - [ ] Narração em português do Brasil: inventariada, não substituída.
- [ ] M8: presets de desempenho (a otimização de compilação já foi feita)
- [ ] M9: launcher e distribuição sem dados do jogo. O app já instala e recompila o jogo
      a partir da cópia do jogador; falta a primeira abertura do jogo pelo app, em
      janela, e o `.dmg` de release.

## 5. Organização

- [x] **Commits pendentes:** as correções do toolkit estão no patch
      `patches/ps3recomp-675ed39-pes13.patch`, aplicado por `tools/setup_toolkit.sh`, e o
      projeto foi enviado em 06/11. O checkout `../ps3recomp-up-r8` continua com as mudanças
      sem commit próprio.
- [x] **`COMPATIBILITY.md`:** linha do 3D e status do M1 corrigidos (M1 ✅, M2 parcial).
- [x] **Logs:** os dois maiores (`boot-24.log` 2,9 GB e `boot-27.log` 1,7 GB) apagados;
      `cache/` caiu de 6,0 GB para 1,4 GB.
- [x] **Arquivo solto:** o `1` na raiz era um frame PPM de 20:32 e foi removido.

## Já resolvido

- Fechamento ao apertar Enter na tela de título.
- Tela de nível que voltava sem avançar.
- Travamento no carregamento depois da configuração.
- Jogadores distantes invisíveis e árbitro preto (tabela de superfícies, volta para a
  memória principal).
- Pele neon e rostos pretos (envio em linha do `NV308A`).
- Uniformes em faixas (pitch dos mipmaps).
- Pose T (`JOBLIST` do SPURS).
- Travamento aleatório na partida (reciclar o anel da FIFO exige 250 ms sem progresso).
- O processo que continuava rodando depois de fechar a janela.
- Tela preta e travamento do DMA (`stop 0x110`).
- Falha do `buffer.tmp` (`PS3_HDD1_ROOT` no `tools/run.sh`).
- `sys_prx_register_library`, `sys_mempool_create` e `sys_mempool_get_count`.

## Versão instalada (2026-11-04)

Disco americano BLUS31029, atualização 01.04, Data Pack 6 e Option File Brasileirão.
Testado sem janela, em pastas separadas: chega ao menu e a uma partida, sem abort, com o
Option File carregado (`EEDIT`, emblemas e uniformes). A abertura com o assistente em
Português do Brasil foi até o carregamento do `EEDIT`.

- **Sem save de opções:** a primeira abertura repete o assistente; escolha Português do Brasil.
- **Em janela, com teclado:** testado em 05/11, um amistoso jogado até o fim.

## Copas e visuais — atualização de 05/11/2026

- [x] Identificar os 203 clubes das três copas (126 Copa do Brasil / 47 Libertadores / 56 Sul-Americana, com sobreposição).
- [x] Conferir 126 identidades CBF por nome e UF; coletar registros dos 89 brasileiros adicionais e referências dos 77 estrangeiros.
- [x] Coletar 210 partidas nacionais para referências de escalação; gerar rascunhos de até 32 candidatos com evidência.
- [ ] Completar elencos profissionais atuais: só 6 dos 89 clubes adicionais têm ao menos 18 candidatos confirmados pelo cruzamento conservador; buscar estaduais/regionais e páginas oficiais atuais.
- [ ] Resolver a falta de lista de atletas do jogo CBF 834781; conferir posições, transferências, lesões e novos contratados.
- [x] Baixar e inspecionar 13 arquivos adicionais de faces da coleção River Plate (26 BINs).
- [ ] Validar identidades/aparência, adaptar faces PC para PS3 e associar IDs sem conflito.
- [ ] Baixar uniformes 1/2 corretos de 2026 para clubes adicionais; kit Rivadavia encontrado é antigo e foi excluído da cobertura atual.
- [ ] Implementar/mapear as competições e validar uma partida completa. Libertadores 2026 e a
      liga sul-americana já estão no perfil de teste (06/11); falta jogar uma partida. A Copa do
      Brasil não cabe no jogo (sem a competição e sem vagas para 126 clubes).

Detalhes e listas: [COMPETICOES_2026.md](COMPETICOES_2026.md).
