# Perfil experimental — 40 clubes A/B

Preparado em 05/11/2026 em `analysis/test-save-brasil-40-2026/`.
Contém 1.054 nomes/números em 40 listas de jogadores, até 32 por clube.
Não substitui os perfis original, Flamengo ou Brasil de 27 clubes.

## Slots dos 13 clubes restantes

Foram reaproveitados os slots genéricos 2470–2482, com validação dos nomes
anteriores antes de escrever. Nenhum clube real foi removido. A ordem é:
Mirassol, Remo, Athletic, Botafogo-SP, CRB, Cuiabá, Fortaleza, Novorizontino,
Juventude, Londrina, Operário-PR, São Bernardo e Vila Nova.
Os nomes dos times foram alterados; IDs dos times e registros de jogadores
continuam os originais. A tabela completa está em
[ROSTERS.md](../analysis/test-save-brasil-40-2026/ROSTERS.md).

**Não são 40 clubes totalmente atualizados.** Atribuição às ligas não mudou:
os novos clubes permanecem nas categorias dos slots genéricos. Abreviações,
escudos, uniformes, formação, atributos, posições, nacionalidade, idade,
rostos/cabelos e nomes de narração ainda são os dados antigos.
Os novos nomes usam registros legados, não identidades PES transferidas.
Referências compartilhadas em outros elencos podem exibir esses nomes também.

Mantém as limitações do [perfil de 27 clubes](SAVE_BRASIL_2026.md). Além dos
conflitos de número já registrados, Athletic tem número 3 repetido na fonte.
Mayk (Remo) e Felipe Vizeu (Avaí) ficaram fora por ausência de confirmação de
clube atual no arquivo de referência. Não inventados substitutos ou números.

## Validação concluída

- 40 IDs de clube distintos; 1.054 IDs de jogador sem repetição entre os alvos.
- Releitura de todas as listas, nomes, números e 13 nomes novos de clubes.
- CRC válido, layout/IDs preservados, alterações somente nos campos permitidos.
- 3.322 recursos de apoio copiados conferidos por hash; original intacto.

Carregamento do novo perfil, acesso aos 40 clubes pelos menus, posições e
partida completa ainda não validados. Havia outra execução ativa durante esta
etapa; ela não foi interrompida nem usada para inferir sucesso deste perfil.
O usuário pediu testar somente depois de ter os 40 preparados; não solicitar
novo teste do perfil parcial de 27 clubes.

Launcher preparado: `tools/testar_brasil_40_2026.command` (sintaxe conferida).
Gerador: `tools/create_brazil_test_save.py --all-clubs`. Ambos usam o perfil
separado; o gerador recusa sobrescrita. Nenhum patch visual ativado. PARAM.PFD
não reassinado: destino é o port local, não PS3 físico.

## Correção de nomes (05/11/2026, noite)

Os 13 clubes colocados nos times genéricos 2470–2482 tinham o nome novo só no
primeiro dos 20 campos de idioma; os outros 19 e a sigla continuavam os do time
genérico (TERZAMOC/TZM, PUNTIHUERVA/PHV...). `tools/set_team_names.py` grava o
nome em todos os idiomas e a sigla, a partir de `team_names.json` do perfil;
o original fica em `DATA.BIN.before-team-names`.

| ID | Antes (1º campo) | Agora | Sigla |
|---:|---|---|---|
| 2470 | MIRASSOL | MIRASSOL | MIR |
| 2471 | REMO | REMO | REM |
| 2472 | ATHLETIC SAF | ATHLETIC-MG | ATC |
| 2473 | BOTAFOGO (igual ao do RJ) | BOTAFOGO-SP | BSP |
| 2474 | CRB | CRB | CRB |
| 2475 | CUIABÁ | CUIABÁ | CUI |
| 2476 | FORTALEZA SAF | FORTALEZA | FOR |
| 2477 | GREMIO NOVORIZONTINO - SAF | NOVORIZONTINO | NOV |
| 2478 | JUVENTUDE | JUVENTUDE | JUV |
| 2479 | LONDRINA SAF | LONDRINA | LON |
| 2480 | OPERÁRIO | OPERÁRIO-PR | OPE |
| 2481 | SÃO BERNARDO SAF | SÃO BERNARDO | SBE |
| 2482 | VILA NOVA | VILA NOVA | VNO |

Conferido: CRC válido, só os campos de nome e sigla desses 13 times mudaram, nenhum
nome novo repete outro time, jogadores intactos, EEDIT original do `rpcs3/` intacto.

Continua errado nesses 13: **escudo e uniformes** são ainda os dos times genéricos, e
eles não estão na liga brasileira do Option File. Os outros 27 usam escudo e
uniformes do próprio Option File. Nada disso foi visto no jogo ainda.

## Séries A e B de 2026 com 20 clubes cada (05/11/2026, noite)

A tabela de ligas do EDIT (210 IDs u16 em 0x516AA6) foi decifrada. A liga 7 (Série B)
tinha 18 vagas fixas no código do jogo. O port agora substitui as três funções que
definem o layout (`port/pes_leagues.cpp`): um save com clube na vaga 190 é lido com a
Série B de 20 vagas a partir da 190 e a liga dos outros europeus com 38 (usava 24);
qualquer outro save, como o Option File original, é lido exatamente como o jogo lia.

`tools/set_leagues.py` grava as ligas; `leagues_2026.json` no perfil tem as duas listas.
O EDIT anterior a isso ficou em `DATA.BIN.before-leagues`.

- Série A (20): Athletico, Atlético-MG, Bahia, Botafogo, Chapecoense, Corinthians,
  Coritiba, Cruzeiro, Flamengo, Fluminense, Grêmio, Internacional, Mirassol, Palmeiras,
  Bragantino, Remo, Santos, São Paulo, Vasco, Vitória.
- Série B (20): América-MG, Athletic-MG, Atlético-GO, Avaí, Botafogo-SP, Ceará, CRB,
  Criciúma, Cuiabá, Fortaleza, Goiás, Novorizontino, Juventude, Londrina, Náutico,
  Operário-PR, Ponte Preta, São Bernardo, Sport, Vila Nova.
- Saíram das ligas (continuam no save, sem liga): Portuguesa, ABC, América-RN, Boa
  Esporte, Figueirense, Guaratinguetá, Joinville, Oeste, Paraná, Paysandu, São Caetano.

Visto no jogo, sem janela: com este perfil o Amistoso mostra "Série B: 20 Times"
começando no América-MG e "Série A: 20 Times"; com o Option File original, "Série B:
18 Times" de ABC a Sport, como antes. Ainda não visto: os dois últimos da Série B na
lista, uma partida, Liga e Master League com 20 na Série B.

Risco conhecido: um trecho do jogo (0x00D37960) insere clubes na liga dos outros
europeus com limite fixo de 40. Com o layout de 20, inserir mais de 14 clubes nela
escreveria sobre a Série B. Nada no uso normal faz isso, mas não está provado.

## Libertadores 2026 (05/11/2026, noite)

A Libertadores do jogo é a competição 27: 38 clubes em vagas por país (ARG 5, BOL 3, BRA 6,
CHI/COL/ECU/MEX/PAR/PER/URU/VEN 3). A lista vem dos dados do jogo, não do EDIT; o port a troca
pela de `gamedata/pes13_competitions.txt` do perfil quando tem o mesmo tamanho
(`port/pes_leagues.cpp`). Sem esse arquivo, o jogo usa a sua.

- Os 32 da fase de grupos de 2026 mais The Strongest, Huachipato, Botafogo, Guaraní, Liverpool e
  Táchira (fase prévia). As vagas do México ficaram com Independiente Rivadavia, Tolima e Botafogo.
- Os 6 brasileiros são os clubes da liga (Flamengo, Fluminense, Cruzeiro, Corinthians, Palmeiras,
  Mirassol): elencos, uniformes e escudos de 2026.
- 13 vagas de clubes de 2013 renomeadas (`libertadores_2026_names.json`); o EDIT anterior ficou em
  `DATA.BIN.before-libertadores`. **Os elencos desses 13 ainda são os do clube antigo**: a tabela
  de elencos das equipes continentais não está decifrada. Os outros estrangeiros têm os elencos
  do Option File (temporada antiga).
- Escudos: pacote `libertadores-2026-escudos` (13 escudos da Wikipédia/Wikimedia, 256x256).
  Uniformes dos estrangeiros: nenhum de 2026 ainda.

Visto no jogo, sem janela: o seletor da Libertadores mostra os 38 clubes de 2026 com os escudos
certos (Cusco não apareceu na captura). Não visto: sorteio, fase de grupos, uma partida da copa.

Para jogar: os três pacotes juntos, `PS3_MODS=libertadores-2026-escudos,brasil-2026-escudos,brasil-2026-uniformes`.

## Elencos de 2026 nos estrangeiros e Sul-Americana (05/11/2026, noite)

Os clubes continentais do jogo (IDs acima de 16000) pegam o elenco do banco de dados do jogo, não
do EDIT. Por isso cada estrangeiro foi para um slot que tem elenco no EDIT: o próprio (Barcelona,
Del Valle, LDU, Cerro, Santa Fe, Tolima, U. Católica, River, Tigre), uma vaga de clube de 2013 que
estava na Libertadores ou um slot genérico (2483–2501, 2514). `tools/apply_continental_2026.py`
com `continental_2026_plan.json` grava em cada um o nome nas 20 línguas, a sigla e o elenco de
2026 (nome, nome na camisa e número; goleiro, 4 defensores, 4 meias e 2 atacantes como titulares).
Jogador que outro elenco também usa (seleção) fica como estava. Atributos, posições e rostos são do
jogador antigo. O EDIT anterior ficou em `DATA.BIN.before-continental`.

- Libertadores (competição 27): os 38 clubes apontam para esses slots.
- Liga Sul-Americana (liga 6, amistosos e liga): os 18 clubes da Sul-Americana 2026 que não estão
  na Libertadores: River, Tigre, Racing, San Lorenzo, Olimpia, Millonarios, América de Cali,
  Palestino, O'Higgins, Audax Italiano, Caracas, Juventud, Cienciano, Blooming, Macará, Cuenca,
  Boston River e Barracas Central. O jogo só tem 18 vagas nessa liga.
- Escudos: `libertadores-2026-escudos` agora tem os 25 da Libertadores que estavam com escudo de
  outro clube e os 16 da Sul-Americana (Wikipédia/Wikimedia, 256x256).

Visto no jogo, sem janela: elenco de 2026 no Boca, na LDU e no Liverpool. No seletor da
Libertadores, escudos certos em todos os que a captura mostrou, dos 38. Na liga do amistoso, 16 de
18 com escudo e nome certos; América de Cali e Cuenca a navegação pulou. A lista da liga no save
tem 18 IDs e 18 nomes diferentes. Os repetidos nas capturas são o cursor parado ou no fim da lista.
Uniformes dos estrangeiros: nenhum de 2026. Não visto: uma partida com esses elencos.

## Faces: sem rosto de outro jogador (06/11/2026)

Os elencos de 2026 foram escritos em registros de jogadores antigos, e cada registro guardava o
rosto do dono anterior: Alan Franco com o rosto do Ronaldinho, Ziyech com o do Seedorf. Dos 2.265
registros renomeados, só 2 eram da mesma pessoa.

No registro do jogador (228 bytes), os bytes 164..191 são o rosto e o cabelo. Copiá-los de outro
registro troca só o rosto e o cabelo: posição, habilidades e físico ficam (visto em Editar >
Jogadores > Rosto, sem janela). `tools/fix_faces_2026.py` grava, em cada jogador renomeado:

- o rosto do próprio jogador, quando o Option File original tem essa pessoa: nome completo numa
  lista conferida à mão (`own_faces.json`) e um só jogador de 2026 com esse nome. São 14: Thiago
  Silva, Alex Sandro, Felipe Anderson, Marcelo Lomba, Éverton Ribeiro, Willian José, Alan Kardec,
  Alan Patrick, Tiago Volpi, Marcos Rocha, Nino Paraíba, Anselmo Ramon, Samuel Xavier e Rodrigo
  Moledo. Nome igual não basta: "J. GARCÍA", "JOÃO VICTOR" e os três "LUIZ GUSTAVO" de 2026 são
  pessoas diferentes. Outros 21 candidatos ficam listados em `faces_2026.json` para revisão.
- nos outros 2.251, o rosto de um jogador fictício dos times genéricos do Option File original
  (843 rostos), diferente para cada jogador do mesmo elenco.

O EDIT anterior ficou em `DATA.BIN.before-faces`. Visto no jogo: Rossi, Pulgar, João Souza e
Luiz com rostos genéricos, e Alex Sandro com o rosto do registro dele (no Option File é um rosto
montado, não uma face real). Não visto: um rosto especial copiado (Thiago Silva).

Ainda falta: os rostos reais de 2026. Não há fonte no formato do PES 2013 para quase nenhum desses
jogadores. Os pacotes TM Games baixados são do PES 2021 (outro mapeamento de textura). Posições e
habilidades também continuam as do jogador antigo.

## Posições e habilidades de 2026 (06/11/2026, em andamento)

Os jogadores renomeados ainda tinham a posição e as habilidades do dono antigo do registro (no
Flamengo, Alex Sandro e Bruno Henrique apareciam como goleiros). Campos do registro, conferidos
com as páginas do PES 2013 no pesdb.net para os mesmos IDs (Iniesta, C. Ronaldo, Daniel Alves,
Fàbregas e mais 30) e com jogadores conhecidos:

| Campo | Onde |
| --- | --- |
| Posição registrada | byte 121, 4 bits de baixo (0 GO, 1 LIB, 2 ZC, 3 LE, 4 LD, 5 VOL, 6 MLG, 7 ME, 8 MD, 9 MAT, 10 PE, 11 PD, 12 SA, 13 CA) |
| Habilidades | bytes 122..147, valor = byte >> 1: ataque 122, defesa 123, equilíbrio 124, resistência 125, velocidade 126, reação 128, explosão 129, drible 130/131, passe curto 132/133, passe longo 134/135, chute 136, força do chute 137, bola parada 139, curva 140, cabeceio 141, salto 142, trabalho em equipe 143, controle 144, raça 146, goleiro 147 |
| Posições que joga | bit 0 de 122 GO, 123 LIB, 124 ZC, 126 VOL, 128 MLG, 130 MAT, 132 SA, 133 CA, 135 LE, 136 LD, 137 ME, 138 MD, 140 PE, 142 PD |
| Pé bom esquerdo | byte 120, bit 7 |
| Pé fraco, forma | byte 148 bits 2..4 (uso − 1); byte 149 bits 2..4 (precisão − 1) e 5..7 (forma − 1) |
| Nacionalidade | bytes 216..217, 9 bits a partir do bit 3 (45 Brasil, 50 Argentina, 49 Uruguai, 48 Paraguai, 47 Chile, 46 Peru, 51 Equador, 44 Colômbia, 104 Bolívia, 105 Venezuela) |
| Idade | byte 218, bits 3..7 = idade − 15 |
| Altura | byte 224, bits 1..7 = altura − 148 cm |

- `tools/collect_pesdb_2026.py` procura cada jogador de 2026 nas cartas base do eFootball
  (pesdb.net). Só aceita a carta quando todos os nomes dela estão no nome completo do jogador, a
  nacionalidade bate, a idade difere no máximo um ano e a altura até 3 cm (onde há esses dados).
  Na dúvida, fica sem carta. As páginas ficam em cache (`--offline` repete sem rede). O site
  limita a velocidade (HTTP 429); a coleta espera e continua.
- `apply_continental_2026.py --mapping` grava qual jogador de 2026 foi para qual registro.
- `tools/set_player_stats_2026.py` grava posição, posições que joga, habilidades convertidas
  da carta, pé, pé fraco, forma, altura, idade e nacionalidade. Sem carta: a posição dos dados
  de 2026 (goleiro pela súmula da CBF; sem nenhuma informação, um palpite pelo número da camisa)
  e as habilidades medianas dos jogadores com carta dessa posição na mesma competição, menos 2.

Calibração: as cartas base do eFootball ficam uns 10 a 12 pontos abaixo da escala do PES 2013
(velocidade média 68 contra 79 na Série A do Option File original). Sem ajuste, o Arthur Cabral
aparecia com geral 50. Cada habilidade é levada para a média e a dispersão dos jogadores da Série A
do Option File original (`--calibrate`), goleiros e jogadores de linha separados; com isso ele fica
com geral 74. Sem carta: no papel geral dos dados de 2026, o número da camisa escolhe lateral (2,
13, 22 / 6, 16), volante (5, 15), meia de armação (10, 20), meia de lado (7, 11) ou ponta; as
habilidades são a mediana calibrada da posição (Série A igual, Série B 4 abaixo, estrangeiros 1).

Aplicado em 06/11/2026 (`DATA.BIN.before-stats` é o EDIT anterior; relatório em `stats_2026.json`):
112 jogadores com carta do eFootball (os 7 primeiros clubes coletados: Athletico, Atlético-MG,
Bahia, Botafogo, Chapecoense, Corinthians, Coritiba) e 2.153 pelo modelo de posição. Visto no
jogo, sem janela, em Editar > Jogadores > Botafogo: posições (Alex Telles LE, Vitinho LD, Ziyech
PTD, Matheus Martins PTE...), habilidades, nacionalidade, idade, altura e geral. A coleta continua;
reaplicar com o `pesdb_2026.json` novo troca o modelo pelos dados reais clube a clube.

## Estádios (06/11/2026)

O jogo tem só três estádios reais brasileiros: Maracanã, Morumbi e Vila Belmiro (Urbano
Caldeira). Dos estádios da Libertadores e da Sul-Americana 2026, só o Monumental (River) existe.
Colocar um estádio 3D novo exigiria converter o modelo inteiro para o PS3; não é feito aqui.

Em Editar > Estádio > Edição de estádios há 34: os 14 do jogo que podem ser renomeados e os 20 do
criador de estádios que vieram no Option File (15 a 34, com as cores de cada clube). No EDIT, cada
um destes 20 é uma entrada de 372 bytes a partir de 0x51FACE: o nome duas vezes (+0 e +97) e depois
as configurações. `tools/set_stadium_names.py` troca só os nomes (`stadiums_2026.json`):

- renomeados para 2026: Ligga Arena, Neo Química Arena, Arena MRV, Arena Condá, Allianz Parque,
  Nabi Abi Chedid, São Januário, Maião, Barradão, Mangueirão (no lugar de Ressacada, Scarpelli,
  Serra Dourada, Independência, Metropolitano, Monumental duplicado, Atahualpa, Pacaembu, Arena
  Pernambuco e Canindé); Minas Arena → Mineirão, Engenhão → Nilton Santos, Grêmio Arena → Arena do
  Grêmio, Casa Blanca → Rodrigo Paz Delgado (LDU);
- mantidos: Fonte Nova, Castelão, Couto Pereira, Beira-Rio, Moisés Lucarelli, Ilha do Retiro.

A aparência de cada um continua a do estádio montado que já estava na vaga. O EDIT anterior ficou
em `DATA.BIN.before-stadiums`. Visto no jogo, sem janela: os 20 nomes na lista. Não visto: uma
partida num deles; se os times usam um estádio de casa, o campo do registro não foi achado.

Outra tabela, de 20 nomes de 0x60 bytes em 0x37B448 (Frasqueirão, Independência...), não aparece
nessa lista. O que ela faz não se sabe; não foi alterada.

## Rostos de 2026 (06/11/2026)

A textura de rosto do PS3 (256x512, DXT1) tem o mesmo layout das faces do PES 2013 de PC
(1024x1024 ou 2048x2048), só que com metade da largura. Ela pode ser trocada por um pacote de
texturas (`PS3_MODS`), em resolução maior: 512x1024, ou 1024x2048 quando a fonte tem 2048.

- Rosto montado não serve de base: jogadores com rostos montados diferentes usam a mesma
  textura. `tools/assign_unique_faces.py` dá a cada jogador com face baixada um rosto especial
  livre (de um jogador de 2013 que saiu do save), com textura própria. A cabeça e o cabelo são
  desse rosto antigo; a textura do rosto vem do pacote.
- `tools/map_face_files.py` liga cada arquivo de face ao jogador de 2026 pelo nome (116 de 170).
- A chave de cada textura é capturada em Editar > Jogadores, linha a linha, com
  `PS3_MODS_DUMP`. Uma chave vista na linha de mais de um jogador é descartada (textura que
  termina de carregar depois que o cursor andou). Duas passadas pelos 20 clubes da Série A.
- `tools/build_face_pack.py` monta o pacote `faces-2026` com 63 rostos de 14 clubes (Flamengo
  13, Bahia 8, Cruzeiro 8, Athletico 5, Corinthians 5, Mirassol 4, Santos 4, Atlético-MG 3,
  Coritiba 3, Fluminense 3, Palmeiras 3, Botafogo 2, Chapecoense 1, Remo 1).

Visto no jogo, sem janela: Pulgar (tatuagens no pescoço e braços) e Arrascaeta (fonte 2048) com
o rosto de 2026, junto com o pacote de uniformes. Os outros 53 ficaram sem chave: o modelo 3D da
linha não carregou a tempo, ou a chave apareceu em mais de uma linha. Uma passada mais lenta
pode completar. Uma execução de teste não aplicou a troca e a causa não foi achada; as três
seguintes aplicaram.

Para jogar: `PS3_MODS=faces-2026,brasil-2026-escudos,brasil-2026-uniformes,libertadores-2026-escudos`.

## Gramado HD (06/11/2026)

O gramado é uma textura de 2048x1024 com o campo inteiro (listras e linhas pintadas), uma por
tipo de estádio (`5edd10acc9e2206d` e `a850e5fc2ea11e06` nas partidas vistas). `tools/make_hd_pitch.py`
gera a versão 4096x2048: o mesmo campo ampliado, com um grão fino de grama só na grama (as linhas
ficam limpas). Pacote `gramado-hd`. Visto numa partida de demonstração sem janela, com
`PS3_RES_SCALE=2` (2560x1440): a troca foi aplicada e o campo fica nítido. Outros estádios podem
usar outra textura de gramado; essas ainda não foram capturadas. Não é uma grama nova, e sim a do
jogo com mais detalhe.

## Placas de 2026 (06/11/2026)

Fonte: pacote de placas do Brasil 2025/26 do LeonardoBorges para PES 2021 (`Brazil Pack.rar`,
baixado pelo dono no navegador; só texturas e modelos, nenhum executável). As artes usadas:
Betano, Assaí, Sicoob, Betnacional (`90systemAd_face_09`) e a faixa "BRASILEIRÃO Betano" (`BR25`).

Os 195 saves `BLUS31029EST_FENCE<nnn>` são as placas, faixas e bandeiras dos 20 estádios do
criador de estádios: cabeçalho de 49 bytes (CRC32 em +8, como os uniformes) e um DDS 512x256 DXT5
com 10 mipmaps; a placa é a faixa opaca da imagem (linhas 84 a 170 na maioria). 70 deles foram
escolhidos à mão como placas de patrocinador de 2013 (Penalty, Lupo, Nike, Coca-Cola, Lotto, BMG,
Samsung, Sky Sports, Carlsberg...); faixas de torcida, bandeiras e peças de estrutura ficaram.
`tools/make_fence_2026.py` refaz a faixa de cada um com três logos ou a faixa do Brasileirão,
recodifica em DXT5 com todos os mipmaps e recalcula o CRC. Lista em `fences_2026.json`, originais
em `backup-fence/`, prévia em `analysis/visual-2026/adboards-2026/preview_fences.png`.

Ainda não visto numa partida: a prévia do editor de estádios não mostra as placas. As placas de LED
"PES 2013" dos estádios oficiais do jogo não mudam (vêm do atlas de logos do menu).
