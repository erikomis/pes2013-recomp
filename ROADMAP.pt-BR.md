# Roadmap

🌐 [English](ROADMAP.md) · **Português (BR)**

Estado do porte nativo do PES 2013 (`BLUS31029`, atualização 01.04) para
macOS/arm64 e o que vem depois. `[x]` = feito e verificado; `[ ]` = a fazer. A
lista de trabalho do dia a dia está em [docs/O_QUE_FALTA.md](docs/O_QUE_FALTA.md).

## Resumo (2026-11-05)

- **Roda:** boot, logos, título, configuração inicial, menus em português,
  seleção de times, escalações, hino e amistosos completos com o Data Pack 6 e um
  Option File. Um amistoso já foi jogado até o fim em janela.
- **Velocidade:** 60,0 fps na partida (p95 17,6 ms) e 30,0 fps nos replays, com
  cerca de 133% de CPU, numa partida sem janela num Mac Apple Silicon livre. Antes
  do trabalho de otimização eram uns 18 fps com 414% de CPU.
- **Som:** o mixer do jogo roda em tempo real sem buracos na partida; um quadro de
  0,1-0,2 s no início do replay ainda perde alguns blocos.
- **Próximo:** esse pico no início do replay; modos de janela, resolução interna,
  filtros de imagem e pacotes de texturas (sendo trazidos); a primeira abertura
  real pelo launcher; um teste de modo carreira.
- **Ainda não:** Windows e Linux, online.

---

## O que falta para ficar 100% jogável

### Bloqueios

- [ ] O pico de um quadro (112-207 ms) quando começa um replay ou troca a cena,
  que é onde estão os buracos de áudio que sobraram. Não é compilação de shader
  (3 shaders novos numa partida inteira). Próximo a perfilar.
- [ ] Confirmar em janela, com a build final e a máquina livre: 60 fps na partida
  e som limpo. Outros processos pesados no Mac derrubam para 15-20 fps.
- [ ] Uma execução de teste sem janela terminou por volta de 490 s sem relatório
  de crash e sem código de saída gravado; a seguinte passou de 590 s. Os scripts
  de teste agora gravam o código de saída. Observar em sessões longas.

### Modos de jogo

- [ ] Master League e Rumo ao Estrelato: criar, salvar, carregar, continuar.
- [ ] Salvar e carregar um Option File editado dentro do jogo.
- [ ] Modos online: devem falhar sem travar offline. Não testado.
- [ ] Troféus (devem ser ignorados offline). Não testado.

### Controles

- [x] Teclado (Enter = START, Espaço = CROSS) e DualSense pelo SDL.
- [ ] Mapear todo o esquema de controle do PES no launcher e testar em janela.
- [ ] Teclado virtual: os nomes são aceitos automaticamente (`PS3_OSK_TEXT`);
  falta um teclado na tela.

### Vídeo

- [ ] Vídeos `.sfd` (fundo do menu, abertura): tocam, mas a decodificação não
  está provada para todos.

---

## Depois de jogável (melhorias)

### Gráficos e resolução

- [x] Resolução interna 1080p / 1440p / 4K (`PS3_RES_SCALE`), na build; o fps de cada degrau ainda não foi medido
- [ ] Pacotes HD: uniformes, escudos, rostos e gramado na resolução das fontes (a imagem do pacote pode ser maior que a textura que substitui)
- [x] Modos de janela, tamanho, monitor, vsync (2026-11-05, na build; ainda não vistos em janela).
- [x] Filtros de imagem: vibração, contraste, vinheta, granulação, LUT de cor e presets (com testes).
- [x] Upscaling espacial MetalFX (com teste; ainda não visto em janela).
- [x] Pacotes de texturas (`PS3_MODS`) e exportação das texturas (um pacote de teste trocou texturas da tela de título sem janela).
- [ ] Ultrawide (visão mais larga, HUD em 16:9 no centro): precisa de um patch de projeção para este jogo.
- [x] Filtro anisotrópico 16x por padrão, FXAA, nitidez.

### Desempenho

- [x] Compilação otimizada: runtime em `-O2`, código convertido em `-O1`.
- [x] Log silencioso por padrão (`PS3_VERBOSE=0`).
- [x] Threads do jogo nos núcleos de desempenho (QoS); vblank de 59,94 Hz.
- [x] Profundidade das sombras convertida na GPU (sem espera pela GPU a cada quadro).
- [x] Constantes de vértice por faixa, memo por programa, pool de buffers, estado
  enviado só quando muda, leitura de vértices pela faixa inteira.
- [ ] Replays a 60: o próprio jogo roda os replays a 30; mudar isso arrisca deixá-los
  em velocidade dobrada. Investigar só depois do resto.

### Brasil 2026

- [x] Ler os elencos do Option File (jogadores, times, CRC) e gravar um save de teste.
- [x] Levantar os 40 clubes das Séries A e B e os participantes das copas de 2026,
  com fontes.
- [x] Séries A e B com 20 clubes cada, nomes em todos os idiomas, elencos de 2026
  dos 40 clubes (2026-11-05, visto sem janela).
- [x] Libertadores 2026 (38 clubes) e a liga sul-americana (18 clubes da
  Sul-Americana) com elencos de 2026; escudos da Wikimedia.
- [x] Uniformes 1 e 2 de 2026 dos 40 clubes, como pacote de texturas (vistos no seletor de times).
- [x] Nenhum jogador com o rosto de outro (14 rostos próprios, os outros fictícios).
- [ ] Posições, habilidades, pé, altura, idade e nacionalidade das cartas do
  eFootball 2026: campos do registro decifrados, ferramenta pronta, coleta rodando.
- [ ] Rostos reais de 2026: 170 faces do PES 2013 de PC baixadas; mostrar uma face
  de PC no PS3 ainda não está provado.
- [ ] Uniformes dos clubes estrangeiros: nenhuma fonte de 2026 encontrada.
- [ ] Uma partida, a Master League e uma Libertadores jogadas com o perfil.
- [ ] Copa do Brasil: o jogo não tem essa competição e o Option File não tem vagas
  para os 126 clubes; só uma copa personalizada com os clubes que existem.
- [ ] Narração em português do Brasil: inventariada, não substituída.

### App para instalar e jogar (launcher)

- [x] App Tauri adaptado do launcher do Resistance 2, com extras do inFAMOUS 2.
- [x] Perfis de Option File (árvore padrão, cópias, pastas de save do PS3, .zip).
- [x] Ajustes honestos: um controle cuja variável não está na build avisa isso.
- [ ] Primeira abertura do jogo pelo app, em janela.
- [ ] `.dmg` de release, instalar e recompilar pelo app.

### Outras plataformas

- [ ] Windows e Linux.

---

## Feito e concluído

### Boot e pipeline

- [x] Disco e atualização inventariados; 01.04 decifrado (NPDRM rev 0x19, licença livre).
- [x] 23.462 funções PPU convertidas; 9 imagens SPU e 2 jobs SPURS convertidos.
- [x] `stop 0x110` (evento recebido pela SPU): a tela preta no boot.
- [x] `PS3_HDD1_ROOT` para o cache do sistema: o carregamento parado.
- [x] Callbacks aninhados do jogo na própria pilha: o fechamento depois do título.
- [x] Eventos do teclado virtual: a página de dificuldade parada.
- [x] Job SPURS sem conversão carregado onde o kernel não o apaga.

### Gráficos

- [x] Jogadores distantes e árbitro (tabela de superfícies, volta para a memória principal).
- [x] Fragment programs completos (envio em linha do NV308A).
- [x] Uniformes sem faixas (pitch dos mipmaps).
- [x] Animação (`JOBLIST` do SPURS).
- [x] Travamento aleatório na partida (reciclar o anel da FIFO exige 250 ms sem progresso).

### Toolkit

Tudo isso está no toolkit compartilhado e ajuda os outros portes também. Vai em
`patches/` e é aplicado pelo `tools/setup_toolkit.sh`.
