# Competições de 2026 — participantes e preparação

Atualizado em 05/11/2026; referência de elencos até 04/11/2026. Este é um levantamento de dados, não um patch instalado.

## Participantes

| Competição | Clubes | Abrangência |
|---|---:|---|
| Copa do Brasil | 126 | Anexo A do regulamento CBF; fases 1/2 ainda precisam do cruzamento com a tabela |
| Libertadores | 47 | Inclui as fases preliminares |
| Sul-Americana | 56 | 44 originais + 4 da fase 3 da Libertadores + 8 terceiros dos grupos |

São **203 clubes distintos** nas três copas: **37** já estavam no levantamento A/B e **166** são adicionais. O trabalho anterior dos 40 clubes A/B continua preservado; a união dos dois escopos tem 206 clubes.

Fontes: [CBF — regulamento e Anexo A](https://stcbfsiteprdimgbrs.blob.core.windows.net/img-site/cdn/REC_Copa_do_Brasil_2026_66989a5426.pdf), [Libertadores](https://gol.conmebol.com/libertadores/es), [Sul-Americana](https://gol.conmebol.com/sudamericana/es), [entradas nos playoffs](https://gol.conmebol.com/sudamericana/es/news/definidos-los-cruces-de-playoffs-de-la-conmebol-sudamericana).

## Elencos e escalações

Conferência adicional em 05/11: a [página oficial do Independiente Rivadavia](https://csir.com.ar/futbol?tab=plantel)
lista 30 profissionais, com números e grupos de posição. Extração reproduzível
por `tools/review_rivadavia_roster.py`; resultado em
`analysis/competitions-2026/official-clubs/rivadavia-roster-review.json`.
29 nomes coincidem com a referência ESPN após normalizar acentos; Fabrizio
Sartori exige confirmação contra Fabrizio Sartori Prieto. Os outros 20 registros
ESPN sem correspondência exata não foram classificados automaticamente como
saídas. A página oficial não informa a data de vigência do elenco: o recorte
exato de 04/11, posições detalhadas, titulares e IDs PES ainda não estão validados.
Esta revisão fica separada da seleção e não modifica o save.

- Reaproveitados os rascunhos dos 37 clubes brasileiros já pesquisados.
- Coletadas referências de elenco de **77 clubes estrangeiros** (2.897 registros de atletas; não equivalem a 2.897 identidades atuais confirmadas).
- Referências adicionais em `analysis/competitions-2026/squad_references.json`, com nomes, números, posições e IDs da fonte.
- As listas podem conter ex-jogadores e atletas da base: verificar clube atual e partidas recentes antes de selecionar até 32 profissionais.
- Os 11 titulares, reservas e formação ainda não estão validados; não inferir escalação pela ordem da API.
- Os **89 brasileiros adicionais** agora têm identidade CBF conferida por nome/UF e 1.483 registros coletados. São referências de inscrições, não 1.483 atletas atuais confirmados.
- Cruzadas **210 partidas** da Copa do Brasil e Séries C/D. O jogo 834781 veio sem lista de atletas; pendência registrada.
- Preparados **495 candidatos** nos 89 clubes, exigindo aparição em partida e nome/UF do clube atual compatíveis. Limite de 32 respeitado; conflitos de clube foram excluídos.
- Somente 6 clubes chegam a 18 candidatos com esses critérios; 85 têm última referência de jogo com mais de 30 dias ou ausente. Ainda faltam fontes atuais, estaduais/regionais, posições e revisão de transferências para concluir os elencos.
- Escalações históricas guardam os 11 titulares e a data; não são automaticamente a escalação atual. Controle por clube: `analysis/competitions-2026/preparation_status.csv`.

## Faces e uniformes 1 e 2

- Os 37 clubes A/B destas copas podem reaproveitar os arquivos do kitpack já baixado; a conversão para PES 2013 PS3 continua pendente.
- Baixados **13 arquivos de faces PES 2013** da coleção River Plate 2025/26; 26 BINs de face/cabelo validados. Sete correspondências de nome nos elencos de referência, ainda sem identidade aprovada ou associação ao jogo.
- Kit Rivadavia 2025/26 baixado (pa/pb 1024×512), mas **reprovado como atual de 2026** por usar Lyon/Macro; a camisa atual usa AIFIT. Não conta como cobertura 2026.
- Clubes adicionais: continuar busca por jogador e uniforme, com temporada, autor, endereço, hash e verificação do conteúdo.
- Kitpack argentino 2026 localizado; download HTTP 403. Faces PES 2013 de Milton Delgado/Carlos Palacios localizadas, com relato de links quebrados no fórum. Não contam como arquivos baixados.
- Fontes e estados em `analysis/competitions-2026/asset_leads.json`. Nenhuma face ou camisa nova desta etapa foi instalada. O pacote Latinoamericano PES21 v7 também retornou HTTP 403 nos dois espelhos.

## Limites da integração

Participantes e imagens não criam uma competição funcional. Ainda é necessário mapear os slots/IDs de clubes e atletas, as tabelas das competições e os formatos de disputa no PES 2013, além de testar o carregamento e uma partida completa. Não substituir slots sem conferir os vínculos existentes.

Arquivos: `participants.json` (identidades e fases), `clubs.csv` (controle), `validation.json` (contagens), `rosters/` (cache ESPN), todos em `analysis/competitions-2026/`.

## Copa do Brasil

| Clube | País / UF | Entrada / grupo |
|---|---|---|
| Flamengo | BRA RJ | 5 |
| Corinthians | BRA SP | 5 |
| Palmeiras | BRA SP | 5 |
| Atlético Mineiro | BRA MG | 5 |
| São Paulo | BRA SP | 5 |
| Fluminense | BRA RJ | 5 |
| Botafogo | BRA RJ | 5 |
| Athletico Paranaense | BRA PR | 5 |
| Bahia | BRA BA | 5 |
| Vasco da Gama | BRA RJ | 5 |
| Cruzeiro | BRA MG | 5 |
| Grêmio | BRA RS | 5 |
| Internacional | BRA RS | 5 |
| Red Bull Bragantino | BRA SP | 5 |
| Santos | BRA SP | 5 |
| Vitória | BRA BA | 5 |
| Coritiba | BRA PR | 5 |
| Mirassol | BRA SP | 5 |
| Chapecoense | BRA SC | 5 |
| Remo | BRA PA | 5 |
| Paysandu | BRA PA | 3 |
| Ponte Preta | BRA SP | 3 |
| Confiança | BRA SE | 3 |
| Barra | BRA SC | 3 |
| Galvez | BRA AC | 1_or_2_pending_ranking |
| Independência | BRA AC | 1_or_2_pending_ranking |
| Vasco | BRA AC | 1_or_2_pending_ranking |
| ASA | BRA AL | 1_or_2_pending_ranking |
| CRB | BRA AL | 1_or_2_pending_ranking |
| CSA | BRA AL | 1_or_2_pending_ranking |
| Penedense | BRA AL | 1_or_2_pending_ranking |
| Amazonas | BRA AM | 1_or_2_pending_ranking |
| Manauara | BRA AM | 1_or_2_pending_ranking |
| Manaus | BRA AM | 1_or_2_pending_ranking |
| Nacional | BRA AM | 1_or_2_pending_ranking |
| Independente | BRA AP | 1_or_2_pending_ranking |
| Oratório | BRA AP | 1_or_2_pending_ranking |
| Trem | BRA AP | 1_or_2_pending_ranking |
| Atlético Alagoinhas | BRA BA | 1_or_2_pending_ranking |
| Jacuipense | BRA BA | 1_or_2_pending_ranking |
| Juazeirense | BRA BA | 1_or_2_pending_ranking |
| Porto | BRA BA | 1_or_2_pending_ranking |
| Ceará | BRA CE | 1_or_2_pending_ranking |
| Fortaleza | BRA CE | 1_or_2_pending_ranking |
| Maracanã | BRA CE | 1_or_2_pending_ranking |
| Tirol | BRA CE | 1_or_2_pending_ranking |
| Capital | BRA DF | 1_or_2_pending_ranking |
| Ceilândia | BRA DF | 1_or_2_pending_ranking |
| Gama | BRA DF | 1_or_2_pending_ranking |
| Desportiva Ferroviária | BRA ES | 1_or_2_pending_ranking |
| Porto Vitória | BRA ES | 1_or_2_pending_ranking |
| Rio Branco | BRA ES | 1_or_2_pending_ranking |
| Anápolis | BRA GO | 1_or_2_pending_ranking |
| Atlético Goianiense | BRA GO | 1_or_2_pending_ranking |
| Goiás | BRA GO | 1_or_2_pending_ranking |
| Vila Nova | BRA GO | 1_or_2_pending_ranking |
| IAPE | BRA MA | 1_or_2_pending_ranking |
| Imperatriz | BRA MA | 1_or_2_pending_ranking |
| Maranhão | BRA MA | 1_or_2_pending_ranking |
| América | BRA MG | 1_or_2_pending_ranking |
| Athletic | BRA MG | 1_or_2_pending_ranking |
| Betim | BRA MG | 1_or_2_pending_ranking |
| Tombense | BRA MG | 1_or_2_pending_ranking |
| Uberlândia | BRA MG | 1_or_2_pending_ranking |
| FC Pantanal | BRA MS | 1_or_2_pending_ranking |
| Ivinhema | BRA MS | 1_or_2_pending_ranking |
| Operário | BRA MS | 1_or_2_pending_ranking |
| Cuiabá | BRA MT | 1_or_2_pending_ranking |
| Mixto | BRA MT | 1_or_2_pending_ranking |
| Operário VG | BRA MT | 1_or_2_pending_ranking |
| Primavera | BRA MT | 1_or_2_pending_ranking |
| Águia de Marabá | BRA PA | 1_or_2_pending_ranking |
| Bragantino | BRA PA | 1_or_2_pending_ranking |
| Castanhal | BRA PA | 1_or_2_pending_ranking |
| Tuna Luso | BRA PA | 1_or_2_pending_ranking |
| Botafogo | BRA PB | 1_or_2_pending_ranking |
| Serra Branca | BRA PB | 1_or_2_pending_ranking |
| Sousa | BRA PB | 1_or_2_pending_ranking |
| Maguary | BRA PE | 1_or_2_pending_ranking |
| Retrô | BRA PE | 1_or_2_pending_ranking |
| Santa Cruz | BRA PE | 1_or_2_pending_ranking |
| Sport | BRA PE | 1_or_2_pending_ranking |
| Altos | BRA PI | 1_or_2_pending_ranking |
| Fluminense | BRA PI | 1_or_2_pending_ranking |
| Piauí | BRA PI | 1_or_2_pending_ranking |
| Azuriz | BRA PR | 1_or_2_pending_ranking |
| Cianorte | BRA PR | 1_or_2_pending_ranking |
| Londrina | BRA PR | 1_or_2_pending_ranking |
| Maringá | BRA PR | 1_or_2_pending_ranking |
| Operário | BRA PR | 1_or_2_pending_ranking |
| Boavista | BRA RJ | 1_or_2_pending_ranking |
| Madureira | BRA RJ | 1_or_2_pending_ranking |
| Nova Iguaçu | BRA RJ | 1_or_2_pending_ranking |
| Portuguesa | BRA RJ | 1_or_2_pending_ranking |
| Sampaio Corrêa | BRA RJ | 1_or_2_pending_ranking |
| Volta Redonda | BRA RJ | 1_or_2_pending_ranking |
| ABC | BRA RN | 1_or_2_pending_ranking |
| América | BRA RN | 1_or_2_pending_ranking |
| Laguna | BRA RN | 1_or_2_pending_ranking |
| Guaporé | BRA RO | 1_or_2_pending_ranking |
| Ji-Paraná | BRA RO | 1_or_2_pending_ranking |
| Porto Velho | BRA RO | 1_or_2_pending_ranking |
| Baré | BRA RR | 1_or_2_pending_ranking |
| GAS | BRA RR | 1_or_2_pending_ranking |
| Monte Roraima | BRA RR | 1_or_2_pending_ranking |
| Caxias | BRA RS | 1_or_2_pending_ranking |
| Guarany de Bagé | BRA RS | 1_or_2_pending_ranking |
| Juventude | BRA RS | 1_or_2_pending_ranking |
| São Luiz | BRA RS | 1_or_2_pending_ranking |
| Ypiranga | BRA RS | 1_or_2_pending_ranking |
| Avaí | BRA SC | 1_or_2_pending_ranking |
| Figueirense | BRA SC | 1_or_2_pending_ranking |
| Joinville | BRA SC | 1_or_2_pending_ranking |
| Santa Catarina | BRA SC | 1_or_2_pending_ranking |
| América | BRA SE | 1_or_2_pending_ranking |
| Itabaiana | BRA SE | 1_or_2_pending_ranking |
| Lagarto | BRA SE | 1_or_2_pending_ranking |
| Guarani | BRA SP | 1_or_2_pending_ranking |
| Novorizontino | BRA SP | 1_or_2_pending_ranking |
| Portuguesa | BRA SP | 1_or_2_pending_ranking |
| Primavera | BRA SP | 1_or_2_pending_ranking |
| São Bernardo | BRA SP | 1_or_2_pending_ranking |
| Velo Clube | BRA SP | 1_or_2_pending_ranking |
| Araguaína | BRA TO | 1_or_2_pending_ranking |
| Capital | BRA TO | 1_or_2_pending_ranking |
| Tocantinópolis | BRA TO | 1_or_2_pending_ranking |

## Libertadores

| Clube | País / UF | Entrada / grupo |
|---|---|---|
| 2 de Mayo | PAR  | 1 |
| Always Ready | BOL  | groups / G |
| Argentinos Juniors | ARG  | 2 |
| Atlético Junior | COL  | groups / F |
| Bahia | BRA BA | 2 |
| Barcelona SC | ECU  | 2 / D |
| Boca Juniors | ARG  | groups / D |
| Bolívar | BOL  | groups / C |
| Botafogo | BRA RJ | 2 |
| Carabobo | VEN  | 2 |
| Cerro Porteño | PAR  | groups / F |
| Coquimbo Unido | CHI  | groups / B |
| Corinthians | BRA SP | groups / E |
| Cruzeiro | BRA MG | groups / D |
| Cusco FC | PER  | groups / A |
| Deportes Tolima | COL  | 2 / B |
| Deportivo La Guaira | VEN  | groups / C |
| Deportivo Táchira | VEN  | 1 |
| Estudiantes de La Plata | ARG  | groups / A |
| Flamengo | BRA RJ | groups / A |
| Fluminense | BRA RJ | groups / C |
| Guaraní | PAR  | 2 |
| Huachipato | CHI  | 2 |
| Independiente Medellín | COL  | 2 / A |
| Independiente Rivadavia | ARG  | groups / C |
| Independiente Santa Fe | COL  | groups / E |
| Independiente del Valle | ECU  | groups / H |
| Juventud | URU  | 1 |
| Lanús | ARG  | groups / G |
| Libertad | PAR  | groups / H |
| Liga de Quito | ECU  | groups / G |
| Liverpool | URU  | 2 |
| Mirassol | BRA SP | groups / G |
| Nacional | URU  | groups / B |
| Nacional Potosí | BOL  | 2 |
| O'Higgins | CHI  | 2 |
| Palmeiras | BRA SP | groups / F |
| Peñarol | URU  | groups / E |
| Platense | ARG  | groups / E |
| Rosario Central | ARG  | groups / H |
| Sporting Cristal | PER  | 2 / F |
| UCV FC | VEN  | groups / H |
| Universidad Católica | CHI  | groups / D |
| Universitario | PER  | groups / B |
| Alianza Lima | PER  | 1 |
| The Strongest | BOL  | 1 |
| Universidad Católica | ECU  | 1 |

## Sul-Americana

| Clube | País / UF | Entrada / grupo |
|---|---|---|
| Academia Puerto Cabello | VEN  | 1 / B |
| Alianza Atlético | PER  | 1 / A |
| América de Cali | COL  | 1 / A |
| Atlético Bucaramanga | COL  | 1 |
| Atlético Nacional | COL  | 1 |
| Atlético Mineiro | BRA MG | groups / B |
| Audax Italiano | CHI  | 1 / G |
| Barracas Central | ARG  | groups / G |
| Blooming | BOL  | 1 / H |
| Boca Juniors | ARG  | playoffs_from_libertadores |
| Bolívar | BOL  | playoffs_from_libertadores |
| Boston River | URU  | 1 / C |
| Botafogo | BRA RJ | groups_from_libertadores / E |
| Carabobo | VEN  | groups_from_libertadores / H |
| Caracas FC | VEN  | 1 / E |
| Cienciano del Cusco | PER  | 1 / B |
| Club Olimpia | PAR  | 1 / G |
| Cobresal | CHI  | 1 |
| Defensor Sporting | URU  | 1 |
| Deportivo Cuenca | ECU  | 1 / D |
| Deportivo Garcilaso | PER  | 1 |
| Deportivo Recoleta | PAR  | 1 / D |
| Deportivo Riestra | ARG  | groups / F |
| Grêmio | BRA RS | groups / F |
| Guabirá | BOL  | 1 |
| Independiente Medellín | COL  | playoffs_from_libertadores |
| Independiente Petrolero | BOL  | 1 / E |
| Independiente Santa Fe | COL  | playoffs_from_libertadores |
| Juventud | URU  | groups_from_libertadores / B |
| Lanús | ARG  | playoffs_from_libertadores |
| Libertad (Ecuador) | ECU  | 1 |
| Macará | ECU  | 1 / A |
| Melgar | PER  | 1 |
| Metropolitanos | VEN  | 1 |
| Millonarios | COL  | 1 / C |
| Monagas SC | VEN  | 1 |
| Montevideo City Torque | URU  | 1 / F |
| Nacional | URU  | playoffs_from_libertadores |
| Nacional Asunción | PAR  | 1 |
| O'Higgins | CHI  | groups_from_libertadores / C |
| Orense | ECU  | 1 |
| Palestino | CHI  | 1 / F |
| Racing (Montevideo) | URU  | 1 |
| Racing Club | ARG  | groups / E |
| Red Bull Bragantino | BRA SP | groups / H |
| River Plate | ARG  | groups / H |
| San Antonio Bulo Bulo | BOL  | 1 |
| San Lorenzo | ARG  | groups / D |
| Santos | BRA SP | groups / D |
| Sporting Cristal | PER  | playoffs_from_libertadores |
| Sportivo Trinidense | PAR  | 1 |
| São Paulo | BRA SP | groups / C |
| Tigre | ARG  | groups / A |
| UCV FC | VEN  | playoffs_from_libertadores |
| Universidad de Chile | CHI  | 1 |
| Vasco da Gama | BRA RJ | groups / G |

