# Créditos

🌐 [English](CREDITS.md) · **Português (BR)**

Este porte só existe por causa do trabalho abaixo. Obrigado a todos.

## Toolkit e base

- **[ps3recomp](https://github.com/sp00nznet/ps3recomp)** — Ned Heller
  ([@sp00nznet](https://github.com/sp00nznet)) e
  [colaboradores](https://github.com/sp00nznet/ps3recomp/blob/master/CONTRIBUTORS.md).
  Runtime, HLE, conversores PPU/SPU e o modelo de projeto (`port/main.cpp`,
  `stubs.cpp`, `CMakeLists.txt` e `config.toml` partem dele). MIT.
- **[NoahBPeterson/ps3recomp](https://github.com/NoahBPeterson/ps3recomp)**
  ([@NoahBPeterson](https://github.com/NoahBPeterson)), o fork do inFAMOUS 1.
  Vários ganhos de velocidade do motor de desenho deste porte (constantes de
  vértice por faixa, memo por programa, leitura de vértices pela faixa inteira,
  decodificação de índices) foram escritos e medidos primeiro para o inFAMOUS 2
  sobre esse fork, e trazidos para cá.
- **Os portes irmãos** — [inFAMOUS 2](https://github.com/erikomis/infamous2-recomp),
  Resistance: Fall of Man, Resistance 2 e Deadpool: o toolkit em que este porte se
  apoia carrega as correções deles, e o launcher partiu do launcher do Resistance 2,
  com as opções de imagem do inFAMOUS 2.

## Referências

- **[RPCS3](https://rpcs3.net)** — a referência de comportamento do PS3, dos
  formatos de savedata e SELF e do gama de saída de vídeo; nunca ligado nem
  distribuído.
- **pfdtool** (flatz) — o formato PARAM.PFD com que o `tools/install_savedata.py`
  decifra o único arquivo protegido do Option File.
- **[Tauri](https://tauri.app)** — o framework do launcher.

## O jogo

Pro Evolution Soccer 2013 © Konami Digital Entertainment. Este projeto não tem
afiliação com a Konami nem com a Sony Interactive Entertainment, e não contém
dados do jogo: cada jogador compila o porte a partir da própria cópia.
