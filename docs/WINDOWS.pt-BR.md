# Windows (x64)

🌐 [English](WINDOWS.md) · **Português (BR)**

O port compila no Windows 10/11 x64 com clang-cl e o backend **Vulkan** do
toolkit, que roda o mesmo motor de desenho (register-file draw engine) do build
Metal. Tudo que é específico do Windows está em `tools/windows/` e em
`patches/ps3recomp-e85647a-pes13-windows.patch`; o build do macOS não mudou.

> [!WARNING]
> **Experimental.** No Windows o PES 2013 chega aos menus e roda o treino a
> 60 fps. Ainda não foram verificados uma partida inteira, uma sessão longa e os
> controles.

## O que você precisa

- Windows 10 ou 11, x64, CPU com AVX2 (qualquer uma de ~2015 para cá), GPU com
  driver Vulkan, uns 25 GB livres no disco do repositório.
- A sua cópia do PES 2013: a imagem do disco americano (`BLUS31029`) em `.iso`
  (ou uma pasta com `PS3_GAME`), a atualização 01.04 e, se quiser, o Data Pack 6
  e um Option File. Como no macOS: nada do jogo está neste repositório.
- O arquivo de chaves do `tools/decrypt_self.py` (veja o topo do script).

## Compilando

```powershell
# uma vez: Git, CMake, Ninja, Python 3.12, LLVM, VS 2022 Build Tools (C++),
# vcpkg com sdl2[vulkan], glslang e vulkan-headers, e o .venv
powershell -ExecutionPolicy Bypass -File tools\windows\install_deps.ps1

# o toolkit, em ..\ps3recomp-pes-win
powershell -ExecutionPolicy Bypass -File tools\windows\setup_toolkit.ps1

# os seus arquivos
#   game\EBOOT.BIN, PARAM.SFO, ICON0.PNG, PS3LOGO.DAT  <- da atualização 01.04
#   game_iso\<o disco>.iso                             <- ou PES_ISO / PES_DISC_DIR
#   tools\self_keys.txt                                <- ou %APPDATA%\pes13-recomp\keys\self_keys.txt
#   BLUS31029_DOWNLOAD\USRDIR, PARAM.SFO               <- Data Pack 6, opcional

# decriptar, analisar, recompilar (PPU, SPU, jobs SPURS), compilar
powershell -ExecutionPolicy Bypass -File tools\windows\rebuild.ps1
```

Um jeito de obter os arquivos da 01.04: instalar o PKG da atualização no RPCS3
e copiar de `dev_hdd0\game\BLUS31029\` (o EBOOT.BIN fica no `USRDIR`).

O `rebuild.ps1` aceita os passos como argumentos (`decrypt analyse lift spu
build`), como o `tools/rebuild.sh`. Só o `build.ps1` recompila depois de uma
mudança; `-Reconfigure` roda o CMake de novo e `-Jobs N` define quantas
compilações em paralelo (padrão: uma a cada 6 GB de RAM). Cada pedaço do código
recompilado tem dezenas de MB de C++, e o build para sozinho se a memória livre
cair abaixo de 10%.

Option File: `tools\install_savedata.py SAVEDATA rpcs3\dev_hdd0\home\00000001\savedata --keys <arquivo>`
com o Python do `.venv`, como no macOS.

## Jogando

```powershell
powershell -ExecutionPolicy Bypass -File tools\windows\run.ps1
```

O `run.ps1` monta a imagem do disco só para leitura (sem precisar de
administrador), monta a árvore de arquivos do jogo em
`rpcs3\dev_hdd0\disc\BLUS31029` com junções de diretório e inicia o jogo. A
saída vai para `cache\boot-last.log` (`PES_LOG=-` mostra no console). Opções vão
depois, como `VAR=valor`, igual ao `tools/run.sh`:

| Opção | O que faz |
| --- | --- |
| `PS3_LANG=PT` | Idioma do console (padrão `PT`), como no macOS |
| `PS3RECOMP_VK_FULLSCREEN=1` | Tela cheia |
| `PS3RECOMP_VK_DEVICE=<n>` | Qual GPU, quando há mais de uma |
| `PS3RECOMP_VK_FPS=1`, `RSX_PACE_LOG=5` | Taxa de quadros; ritmo dos quadros a cada 5 s |
| `PS3_RES_SCALE=1080p\|1440p\|4k` (ou `1`..`4`) | Resolução interna: cada alvo de renderização esse tanto de vezes os 720p do PS3, reduzido para a janela (supersampling; padrão `1`) |
| `PS3_ANISO=16` | Filtro anisotrópico onde o jogo usa mipmaps (padrão `16`; `0` = o do jogo) |
| `PS3_AA=smaa` | SMAA 1x no quadro, na resolução interna |
| `PS3_SHARPEN=0..1`, `PS3_VIBRANCE=-1..1`, `PS3_CONTRAST=0.5..1.5` | Nitidez AMD CAS, vibrância, contraste (um passe só) |
| `PS3_VSYNC=1` | Espera o monitor (FIFO); o padrão é MAILBOX, que nunca bloqueia e não rasga a imagem |
| `VK_DRAW_BATCH=0` | Um envio e uma espera por desenho, como antes (padrão `1`; sem ele, cerca de metade da taxa de quadros) |
| `VK_DRAW_BATCH_ASYNC=1`, `PES_SPLIT_PRESENT=1` | Lotes e apresentações que não esperam a GPU. Desligados por padrão: com eles, os uniformes quebravam em cerca de metade das partidas em 4K interno |
| `PES_EVENTS=0`, `PS3_PAD_SPEAKER=0`, `PS3_PAD_LIGHT=#rrggbb` | Os efeitos de partida no DualSense, como no macOS |
| `PS3_VERBOSE=1` | O log completo do runtime (muito grande) |

Controles: DualSense, DualShock 4, Xbox e os outros que o SDL conhece, com
vibração (o toolkit é compilado com `PS3RECOMP_PAD_SDL2`). Sem controle, o
teclado é o controle 1: setas o direcional, Z/X/A/S xis/bola/quadrado/triângulo,
Q/W L1/R1, 1/2 L2/R2, Enter START, Tab SELECT. Fechar a janela encerra o jogo,
depois de terminar um save em andamento.

## Diferenças para o build do macOS

- **Toolkit.** O macOS compila contra erikomis/ps3recomp `675ed394` mais
  `patches/ps3recomp-675ed39-pes13.patch`. O Windows compila contra o master do
  sp00nznet/ps3recomp em `e85647a3`, que já tem o backend Vulkan no Windows,
  build com clang-cl, helpers de SPU em SSE4.1/AVX2 e áudio WASAPI, com as
  mudanças deste port no toolkit mescladas por cima
  (`patches/ps3recomp-e85647a-pes13-windows.patch`). A maioria já estava no
  upstream; o resto veio junto: ids de semáforo com geração (o travamento do
  Master League), a cópia de volta para a memória dos alvos pequenos em memória
  principal (os uniformes dos jogadores distantes), os relatórios da GPU em
  memória principal no IO `0x0E000000`, o overrun do FIFO que precisa persistir
  antes de reciclar, os GETLLAR em espera que dormem em vez de girar, os efeitos
  de partida no DualSense, a contagem de saves em andamento que a saída espera, e
  o resto do patch do macOS onde não é Metal.
- **O que é só do Metal ainda não existe aqui:** MetalFX, FXAA, a LUT de cor e
  o grão, pacotes de
  texturas (`PS3_MODS`: o gramado HD, as faces e uniformes de 2026), o teclado
  virtual nativo e a escolha do dispositivo de áudio. O backend Vulkan precisaria
  de cada um deles.
- **O launcher** (`launcher/`) por enquanto é só macOS.

## O que foi verificado (27/11/2026, Ryzen 5 5600, RTX 4070 Ti SUPER)

- O `setup_toolkit.ps1` a partir de um clone novo dá exatamente a árvore com que
  o build foi feito (mesmo hash de árvore do git).
- O runtime do toolkit e o executável, o scaffold e as substituições do port
  compilam com clang-cl 23 e linkam com lld-link; as definições do port para as
  funções recompiladas que ele substitui vencem as versões weak (conferido no
  mapa do link).
- O título sintético de boot do toolkit (`tools/make_smoke_elf.py`) passa pelo
  `PES2013Recomp.exe`: loader, NIDs, threads do jogo, FIFO, flips e vblank, no
  backend Vulkan fora da tela e numa janela Win32, pelo `run.ps1` (ISO montada,
  junções criadas, PARAM.SFO lido através delas).
- `ppu_loader.py` e `ppu_lifter.py` rodam no Windows num EBOOT real de 10 MB (de
  outro jogo): 14 arquivos, 1,7 GB, 4 minutos; o `weaken_lifted.py` os lê.

- O PES 2013 recompilado abre com o disco BLUS31029 e a atualização 1.04, salva
  a configuração inicial e chega ao menu principal. O patch do toolkit corrige
  os caminhos absolutos no cache EDAT do Windows para que `dt10.sdat` seja lido
  corretamente.
- O mixer no Windows usa intervalos regulares e aplica às threads PPU o limite
  de prioridade configurado pelo script de execução. Em 30 segundos de menu
  após a inicialização, a proporção de blocos de áudio vazios caiu de cerca de
  85% para 0,3%. O WASAPI não registrou descarte de quadros nas duas capturas.
- O Vulkan sincroniza o envio de texturas e a escrita em alvos de renderização
  antes que os shaders os leiam, inclusive com o agrupamento de desenhos desativado.
- Agrupamento de desenhos (`VK_DRAW_BATCH=1`, agora padrão no `run.ps1`): no
  treino a taxa foi de ~30 fps (p95 de 80-95 ms; o FIFO levava 30-90 ms por
  quadro com um envio e uma espera por desenho) para 59,9 fps (p50 16,6 ms, p95
  20 ms), com a mesma imagem. Áudio nas mesmas execuções: 187,5 blocos/s, 0% de
  silêncio, nenhum underrun.
- Resolução interna (`PS3_RES_SCALE`): partidas em 1440p e 4K internos saem
  corretas (jogadores, uniformes, arquibancada, torcida, sombras, HUD, replays
  com profundidade de campo) numa tela 1920x1080, a 60 fps (4K: p50 16,7 ms,
  p95 18,7-23 ms, GPU em ~40%). O que fez diferença foi o swapchain em
  MAILBOX em vez de FIFO (cada aquisição esperava um vblank).
- Uniformes quebrados em 4K interno: com os lotes em dois slots
  (`VK_DRAW_BATCH_ASYNC`) e a apresentação dividida (`PES_SPLIT_PRESENT`)
  ligados, cerca de metade das partidas mostrava jogadores com partes do
  uniforme faltando ou erradas: cores de outro time nas mangas, tronco preto ou
  transparente, calção e pernas sumindo. Com os dois desligados: nenhuma em
  quatro partidas, e a partida ainda a 58-60 fps em 4K com SMAA. Os dois agora
  vêm desligados. Nada que o jogo lê espera por eles, então provavelmente
  expõem uma corrida de tempo em outro lugar (o jogo monta os uniformes nas
  SPUs) em vez de causá-la; isso continua em aberto.
- SMAA e CAS (`PS3_AA=smaa PS3_SHARPEN=0.3`), desenhados com os próprios
  pipelines do motor: 57-60 fps em 1x e em 4K interno, bordas suavizadas.

## Upscalers temporais (DLSS, FSR 3/4) e geração de quadros

Não estão aqui, e não é questão de ligar uma opção. DLSS (qualquer versão), FSR
3.1 e FSR 4 são temporais: precisam de vetores de movimento por pixel, da
profundidade do quadro e de um jitter na projeção do jogo, e o quadro do PS3 não
tem nada disso. O port do God of War: Ascension (rigaz29/Ascension-R) tem DLSS e
FSR 4.1 porque estudou o renderizador daquele jogo: as matrizes de câmera, o
buffer de velocidade do motion blur, onde começa o HUD. O PES 2013 precisaria do
mesmo estudo do renderizador dele. O modelo do FSR 4 também só roda em AMD
Radeon (em NVIDIA o SDK do FSR cai para o FSR 3.1), e o DLSS 5 foi anunciado
para a série RTX 50. Renderizar em 4K interno e reduzir para a tela já dá o
principal do que um upscaler daria aqui.
