# Faces e uniformes encontrados — 05/11/2026

## Faces baixadas

Fonte do autor: [Faces Brasileirão TM Games](https://pes-edition.foroactivo.com/t655-faces-brasileirao-tm-games).
Foram baixados 19 ZIPs (141.167.844 bytes), cobrindo 18 nomes de clubes; Vitória
possui dois packs. São complementos, não elencos completos. Inventário: 143
arquivos cujo nome indica face, além dos cabelos; 427 cabeçalhos DDS encontrados.
Nenhum pacote foi instalado ou executado. A identidade dos jogadores e a
atualidade da aparência ainda precisam ser revisadas.

Clubes indicados pelos arquivos: Mirassol, Palmeiras, Bragantino, Remo, Vitória,
São Paulo, Santos, Grêmio, Fluminense, Flamengo, Cruzeiro, Coritiba, Corinthians,
Chapecoense, Botafogo, Bahia, Atlético e Athletico. O nome de um ZIP não comprova
seu conteúdo: a própria discussão contém relatos de links trocados. Confirmar
cada atleta antes de associar ao elenco. Não há cobertura completa das Séries A/B.

No Flamengo, a inspeção encontrou Andrew, Evertton Araújo, Pulgar e Jorge
Carrascal, cada um com face e cabelo. As quatro faces contêm textura principal
1024×1024 DDS (DXT1/DXT5). Os arquivos são WESYS comprimidos com zlib, formato
PC; não equivalem aos saves EFACE de PS3. O inventário registra bytes adicionais
após o fluxo zlib, sem descartar ou modificar esses dados.

Arquivos em `analysis/visual-2026/sources/`:

- `face-pack-downloads.json`: links, hashes e membros de cada ZIP.
- `downloaded-face-formats.json`: formatos e dimensões DDS inspecionados.
- `Flamengo2026.zip` e os outros 18 pacotes originais.

Reproduzir inspeção: `tools/inspect_downloaded_faces.py analysis/visual-2026/sources`
com o Python compartilhado. Não extrai caminhos dos arquivos nem executa conteúdo.

## Uniformes encontrados

- [SENNIN.DEV — Flamengo titular 2026, PES 2021](https://www.sennin.dev/2026/07/pes-2021-flamengo-kit-home-2026.html).
  Página do criador consultada e preservada. Link ShareMods respondeu HTTP 403;
  arquivo de uniforme não baixado. Conversão de atlas/modelo para PES 2013 ainda
  necessária; não serve diretamente no EUNIFORM do PS3.
- [Kitpack Campeonato Brasileiro 2026 para PES 2021](https://pes-files.com/pes-2021-campeonato-brasileiro-kitpack-2026/).
  Divulgação atribui a Games de PC e anuncia A/B; conteúdo não baixado nem
  validado. Fonte secundária, não prova cobertura ou fidelidade de todos os times.
- [Coleção Flamengo PES 2013 2025/26](https://www.pesfooty.com/2026/01/cr-flamengo-face-collection-202526.html):
  alternativa para jogadores ausentes; instalação anunciada via Kitserver PC.

## Próximo passo

Mapear cada arquivo ao jogador certo, comparar os formatos com os recursos do
disco PS3 e preparar a conversão em cópia separada. Resolução 1024×1024 medida
não comprova fidelidade nem integração com o motor. Não substituir arquivos
EFACE/EUNIFORM por BINs de PC. O save de teste continua com as faces antigas.

## Continuação — cobertura por clube

Adicionado o pack complementar `facepack_tm_games.zip` do mesmo autor:
9.332.411 bytes, oito faces e oito cabelos. Inspeção WESYS/DDS concluída;
manifesto e hash em `sources/tm-extra-formats.json`. Total local: 20 ZIPs,
151 arquivos de face, não necessariamente 151 jogadores distintos.

`tools/report_visual_coverage.py` cruza nomes de arquivo com os 1.054 atletas
selecionados e gera `docs/COBERTURA_VISUAL_2026.md` e
`analysis/visual-2026/coverage/{coverage.json,clubs.csv}`. São 125 jogadores com
alguma coincidência de nome, sem revisão de identidade. O cruzamento pesquisa
todos os packs para não perder jogadores transferidos; pode sugerir homônimos.
Nenhuma correspondência é automaticamente aplicada.

A meta exige 80 uniformes (titular/reserva de cada um dos 40 clubes). A/B 2026
anunciado com 374,96 MB: ModsFire `https://modsfire.com/D8Cyl077QAaT6V6` e
ShareMods `https://sharemods.com/raq5fkkegfxy/PES_2021_kits_Campeonato_Brasileiro.rar.html`.
Ambos responderam HTTP 403 ao download via ambiente local. Consulta web chega
à página intermediária, mas não entrega o arquivo. Não baixado, cobertura não
confirmada. Fontes alternativas localizadas: face Paulinho/Internacional por
m4rcelo, https://www.kazemario.com/2026/04/pes-2013-paulinho-face.html, e coleção
Vasco PES21 https://pes-files.ru/pes_2021_cr_vasco_da_gama_faces_2026; ainda não
baixadas ou convertidas. Nenhuma compra/assinatura foi efetuada.

## Kitpack recebido e verificado — 05/11/2026

A pendência de download acima foi resolvida pelo dono do projeto. O RAR e
os arquivos extraídos estão em `sources/kitpackAB2026/`. Na auditoria local
foram confirmadas 40 pastas de clubes e 80 texturas de p1/p2 referenciadas por
KitFile nos config.txt, todas presentes e com assinatura FTEX. Inventário
reproduzível: `tools/inventory_kit_slots.py`, saída `coverage/kit_slots.json`,
com hashes e caminhos por slot. A cobertura JSON/CSV/Markdown foi atualizada.

p1/p2 são candidatos a titular/reserva, ainda não conferidos visualmente com os
uniformes oficiais. Botafogo lista p1,p3 como primeiros; Fluminense lista
p1x1,p2. Não selecionar cegamente as duas primeiras entradas de order.ini.

Ainda não há conversão nem instalação desses arquivos. uniform_texture.py
aceita uma imagem RGBA 256x256 de overlay; NÃO converte FTEX nem transforma
automaticamente o atlas completo de PES21 em uniforme PS3. É necessário
extrair/decodificar a textura, adaptar o desenho e mapear seu vínculo no jogo.
O perfil experimental do Flamengo segue com as faces/uniformes antigos.

## Busca complementar de faces — 05/11/2026

Novas pistas registradas em `sources/face-search/leads.json`, sem incrementar
contagem de arquivos baixados: Robert Renan PES13 (m4rcelo, 2024); Internacional
PES13 (m4rcelo, 2023); Internacional PES21 (2025, inclui Braian Aguirre, Bernabei,
Bruno Gomes, Thiago Maia e Rochet); Estoril PES21 2024/25 e Santos PES21 2025
(incluem Zanocelo); Bragantino PES20/21 2021 (inclui Alerrandro).

Lucas Piton PES13/2020: link original Mediafire retornou 404. Internacional
PES13: página intermediária preservada e link original identificado como
https://ouo.io/gUFYKNx, arquivo ainda não obtido. As fontes anteriores a 2026
são alternativas de aparência para revisão, não comprovação de rosto atualizado.
Nenhuma destas novas pistas foi instalada ou contada como face disponível.
