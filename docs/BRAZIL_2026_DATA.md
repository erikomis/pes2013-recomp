# Brasileirão A e B — atualização 2026

Recorte solicitado: elencos mais recentes até **04/11/2026**.
Estado em 05/11: **novo perfil experimental separado com 1.054 nomes/números e
listas dos 40 clubes aplicado**. Os 13 restantes usam slots genéricos 2470–2482.
Posições, atributos, aparências e ligas permanecem antigos. O original não mudou.
Ver [SAVE_BRASIL_40_2026.md](SAVE_BRASIL_40_2026.md): integridade dos dados validada,
carregamento/partida e acesso aos clubes pelos menus ainda não confirmados.
O perfil anterior de 27 clubes continua preservado.
Alvo local: PES 2013 PS3 BLUS31029, atualização 01.04, Data Pack 6.

Decisão do usuário: **até 32 jogadores do profissional por clube**, priorizando
participação recente. Não preencher slots automaticamente com atletas da base.

## Entrega de preparação em 04/11/2026

### Avanço mais recente

O bloqueio das fichas individuais foi contornado pelo uso de **listas públicas de
partidas**, com menos consultas: 62 partidas, três recentes por clube, todas
coletadas sem erro. Resultado: **1.054 candidatos únicos nos 40 clubes**, de 24
a 30 por equipe, cruzados com o clube atual da CBF. Não há jogador selecionado
em dois clubes. Estar relacionado pode significar banco, não minutos jogados.

A ESPN forneceu **1.862 registros de elenco para a temporada 2026**, com posições,
nascimento, nacionalidade e dados físicos. Foram obtidas 918 sugestões únicas de
correspondência por nome e 136 casos sem correspondência única. Identidades ainda
não aprovadas: nomes parecidos e homônimos exigem revisão. Divergências de número
e de classificação como goleiro são preservadas, não corrigidas por suposição.

**Arquivo principal desta etapa:**
[STATUS.md](../analysis/brasil-2026-review/STATUS.md).
Lista para revisão: [recent_professionals.csv](../analysis/brasil-2026-review/recent_professionals.csv).
JSON: `analysis/brasil_2026_candidate_squads.json`.
O arquivo anterior `brasil_2026_draft.json` continua sendo o resultado incompleto
da coleta de fichas individuais; não é o resultado novo baseado nas partidas.

O [Flamengo](../analysis/brasil-2026-review/FLAMENGO.md) tem uma referência adicional
dos 27 profissionais da página oficial, com posições e IDs CBF. A escalação de
29/10 aponta Paquetá 11 e João Victor 61, enquanto a página de elenco conserva
20 e 71. Ambos os valores e suas fontes ficam no JSON de referência.

Ferramentas novas: `collect_recent_squads.py`, `collect_espn_squads.py` e
`merge_squad_evidence.py`. As duas coletas usam cache e interrompem a rede após
três falhas consecutivas. Dados de lesão, reforços sem partidas recentes, posições
específicas, atributos, IDs PES e ligas ainda precisam de revisão/implementação.
Na etapa original nenhuma lista havia sido aplicada. Em 05/11, os registros
confirmados dos 27 clubes mapeados foram usados no perfil experimental acima;
isso não valida as propostas de identidade/posição nem o carregamento em jogo.

Visual e importação de uniforme: ver [VISUAL_2026.md](VISUAL_2026.md).

### Inventário inicial e coleta de fichas

- 2.050 registros de atletas nas páginas oficiais dos 40 clubes, com ID CBF,
  nome completo, apelido, clube atual, UF e URL da fonte.
- 18 identidades com informações conflitantes, separadas para revisão.
- 99 fichas individuais com nascimento, vínculo e histórico de partidas coletadas.
  Depois disso, consultas falharam repetidamente; uma consulta de diagnóstico
  retornou `Connection reset by peer`. A coleta foi interrompida. Não está provado
  se a causa é limite da CBF ou da conexão. O cache permite retomar depois.
- 27 clubes associados por nome a slots domésticos existentes no Option File;
  13 ainda exigem definição de slot. Isso não confirma suas divisões no jogo.
- Leitor local extrai 8.993 registros de jogadores, 417 registros de nomes de times
  e 340 elencos principais. Todos os jogadores desses elencos têm referência válida.
- Save original permanece com o mesmo SHA-256 da inspeção inicial.

Arquivos locais (dados derivados não devem entrar em commit):

- [Relatório por clube](../analysis/brasil-2026-review/REVIEW.md)
- [Lista de atletas e fontes em CSV](../analysis/brasil-2026-review/athletes.csv)
- [Mapeamento proposto de clubes](../analysis/brasil-2026-review/team_mapping.json)
- `analysis/brasil_2026_cbf.json`: registros oficiais coletados.
- `analysis/brasil_2026_draft.json`: evidências enriquecidas. **Nenhum clube tem
  cobertura completa de fichas**, portanto as listas finais de 32 estão vazias.
- `analysis/brasil_2026_existing_rosters.json`: banco antigo lido do save.

Clubes sem correspondência doméstica encontrada: Mirassol, Remo, Athletic,
Botafogo-SP, CRB, Cuiabá, Fortaleza, Novorizontino, Juventude, Londrina,
Operário-PR, São Bernardo e Vila Nova.

## Formato observado e limites

`tools/pes2013_edit.py` é um leitor específico para o arquivo local de 7.905.992
bytes e cabeçalho `01000601`. Rejeita checksum inválido e referências quebradas.
Não é um editor universal e não contém rotina de gravação.

| Campo | Localização observada |
|---|---|
| CRC32 big-endian | `0x08`, calculado no arquivo inteiro com esses 4 bytes zerados |
| Jogadores base | `0x20`, 12.000 slots de 228 bytes; ID `0xFFFFFFFF` indica slot ignorado |
| Jogadores criados | `0x516C4C`, 160 registros observados de 228 bytes |
| Nome do jogador | registro + 50, UTF-8, campo de 46 bytes |
| Nome na camisa | registro + 96, UTF-8, campo de 18 bytes |
| Nomes de equipes | `0x29BFA0`, stride 1.460; 417 registros preenchidos observados |
| ID da equipe | registro de nome + 1.456, 16 bits big-endian |
| Elencos principais | `0x383B48`, 340 registros observados de 164 bytes |
| Inscrições | elenco + 4, 32 IDs de 32 bits big-endian |
| Camisas | elenco + 132, 32 números de 1 byte |

Offsets inferidos por inspeção local e conferência cruzada de referências. Não
validados por uma edição seguida de carregar/salvar no jogo. Equipes continentais
têm IDs distintos; suas tabelas de inscrição ainda não estão mapeadas. Não usar
automaticamente os elencos domésticos para substituir essas variantes.

## Reproduzir e retomar

```sh
../deadpool-recomp/tools/.venv/bin/python tools/pes2013_edit.py \
  rpcs3/dev_hdd0/home/00000001/savedata/BLUS31029EEDIT/DATA.BIN \
  > analysis/brasil_2026_existing_rosters.json
../deadpool-recomp/tools/.venv/bin/python tools/enrich_cbf_rosters.py \
  analysis/brasil_2026_cbf.json --cache analysis/cbf-2026-11-04/profiles \
  --output analysis/brasil_2026_draft.json --offline
../deadpool-recomp/tools/.venv/bin/python tools/report_brazil_rosters.py \
  analysis/brasil_2026_draft.json analysis/brasil_2026_existing_rosters.json \
  --out-dir analysis/brasil-2026-review
../deadpool-recomp/tools/.venv/bin/python -m unittest discover \
  -s tools -p 'test_roster_tools.py' -v
```

Para retomar consultas quando a conexão estiver disponível, remover `--offline`.
A ferramenta reutiliza fichas em cache, consulta sequencialmente com intervalo e
interrompe a rede após 3 falhas consecutivas. As páginas são dinâmicas: uma consulta
em data posterior exige revisão do recorte, não comprova sozinha o vínculo em 04/11.
Posições e camisas de 2026 ainda precisam de fonte; os números antigos do save não
foram reaproveitados como se fossem atuais.

## Clubes confirmados

Participantes conferidos nas listas oficiais da CBF em 04/11/2026:
[Série A](https://www.cbf.com.br/futebol-brasileiro/times/campeonato-brasileiro/serie-a/2026)
e [Série B](https://www.cbf.com.br/futebol-brasileiro/times/campeonato-brasileiro/serie-b/2026).
Esta confirmação é dos clubes participantes; não comprova os elencos.

| Série A | Série B |
|---|---|
| Athletico-PR | América-MG |
| Atlético-MG | Athletic-MG |
| Bahia | Atlético-GO |
| Botafogo-RJ | Avaí |
| Chapecoense | Botafogo-SP |
| Corinthians | Ceará |
| Coritiba | CRB |
| Cruzeiro | Criciúma |
| Flamengo | Cuiabá |
| Fluminense | Fortaleza |
| Grêmio | Goiás |
| Internacional | Novorizontino |
| Mirassol | Juventude |
| Palmeiras | Londrina |
| Red Bull Bragantino | Náutico |
| Remo | Operário-PR |
| Santos | Ponte Preta |
| São Paulo | São Bernardo |
| Vasco da Gama | Sport |
| Vitória | Vila Nova |

## Inspeção local

O pacote original `SAVEDATA/BLUS31029EEDIT` tem arquivos datados de maio de
2013. A data do arquivo sozinha não determina a temporada de seu conteúdo.
Não há evidência de atualização 2026 no pacote inspecionado.

O `DATA.BIN` instalado tem 7.905.992 bytes e já está descriptografado pelo
instalador local. Nomes são legíveis em UTF-8: `NEYMAR` em `0x9A522`,
`CORINTHIANS` em `0x2E78B3`, `FLAMENGO` em `0x2E7E67`.
Isso permite investigar o banco, mas não estabelece os IDs nem os vínculos.
Os saves não foram alterados nesta inspeção.

Reproduzir (somente leitura; resultado derivado fica em `analysis/`):

```sh
../deadpool-recomp/tools/.venv/bin/python tools/inspect_edit.py \
  rpcs3/dev_hdd0/home/00000001/savedata/BLUS31029EEDIT/DATA.BIN \
  --text CORINTHIANS --text FLAMENGO --text NEYMAR \
  > analysis/brasil_2026_edit_inventory.json
```

## Trabalho necessário antes de aplicar

- Mapear registros, IDs, inscrições, slots de competição e checksums do EEDIT.
- Reunir os jogadores de cada clube em fontes datadas: nome, posição, número,
  nascimento e vínculo vigente. Distinguir inscrito na temporada de atleta ainda
  no elenco na data de corte; registrar empréstimos e saídas.
- Identificar jogadores existentes e novos sem confundir homônimos. Atributos
  de PES exigem critério próprio; não são dedutíveis de uma lista de atletas.
- Gerar alterações numa cópia, com backup, manifesto e reversão; verificar os
  40 clubes, inscrições duplicadas e referências a jogadores inexistentes.
- Validar carregamento, escalações, partida e salvar/carregar em perfil isolado.

Uniformes, escudos e faces 2026 precisam de validação separada dos elencos.
O anúncio de patch 2025/26 citado no plano não comprova os 40 elencos nem sua
compatibilidade com este save. Nenhum pacote externo foi instalado.

## Cruzamento com jogadores do PES — 04/11/2026

`tools/propose_pes_identities.py` cruza somente os 1.054 selecionados por nomes
normalizados, preservando homônimos. Resultado em
`analysis/brasil-2026-review/pes_identity_candidates.json`: 152 correspondências
únicas de nome, 243 ambíguas e 659 sem correspondência. Todas são propostas
NÃO verificadas, inclusive as únicas; diferenças entre 2013 e 2026 tornam
nome igual insuficiente. Nenhum ID de face foi atribuído nem save modificado.
Teste sintético confirma preservação de homônimos e exclusão de não selecionados.

## Ampliação para as copas — 05/11/2026

Participantes e pendências de Libertadores, Sul-Americana e Copa do Brasil estão em [COMPETICOES_2026.md](COMPETICOES_2026.md). São 203 clubes nas copas, com 37 rascunhos A/B reaproveitados e referências de 77 clubes estrangeiros coletadas. Os 89 brasileiros adicionais têm registros CBF e referências de partidas coletados; 495 candidatos foram preparados, mas os elencos continuam incompletos e pendentes de revisão atual. Essa ampliação não foi instalada no save.
