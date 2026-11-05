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
