# Visual e conteúdo Brasil 2026

Alvo: BLUS31029 01.04 + Data Pack 6. Escopo de conteúdo: Brasileirão A e B,
até 32 profissionais por clube, com recorte de 04/11/2026.

## O que já mudou

### Galeria local para conferir os uniformes — 05/11/2026

[Abrir a galeria dos 40 clubes A/B](../analysis/visual-2026/kit-review/index.html).
São 82 prévias: p1/p2 de cada clube e as alternativas p3 do Botafogo e p1x1 do
Fluminense, indicadas na ordem do kitpack. Originais FTEX 2048×2048 preservados;
as prévias são 512×512 com alpha opaco apenas para visualizar as cores do atlas.
Não são imagens do uniforme vestido nem arquivos prontos para instalar no PS3.

`tools/preview_kit_slots.py` usa o conversor FTEX existente. Manifesto e validação
em `analysis/visual-2026/kit-review/`: 82 PNGs sem erro, CRCs e hashes dos PNGs e
originais conferidos, cobertura p1/p2 dos 40 clubes. Temporada, patrocinadores,
ordem titular/reserva e adaptação UV ao PES 2013 continuam pendentes. O slot p3
do Botafogo, por exemplo, aparece preto na prévia; a ordem do pacote não basta
para decidir qual é o uniforme reserva. Nenhum desses arquivos foi instalado.

`tools/run.sh` usa `PS3_ANISO=16` por padrão. A opção já existe no backend Metal
e foi localizada no executável. Aplica filtragem anisotrópica aos samplers
lineares com mipmaps; ajuda texturas vistas em ângulo. Não aumenta a resolução
das texturas nem muda iluminação, modelos, faces ou elencos.

Sintaxe do runner conferida. Não foi feita comparação visual ou de desempenho
16× versus original neste trabalho. Para comparar:

```sh
tools/run.sh PS3_ANISO=0
tools/run.sh PS3_ANISO=8
tools/run.sh PS3_ANISO=16
```

## Uniformes: formato local mapeado

Os 389 saves `BLUS31029EUNIFORM*` instalados têm 262.179 bytes. Na variante
inspecionada, há 32 bytes de cabeçalho, flag no byte 32, uma imagem RGBA8 de
256×256 a partir do byte 33 e 2 bytes finais. CRC32 big-endian em +8,
calculado com esse campo zerado. Exportação visual conferida em um uniforme;
os 389 passaram pelo teste de exportar e reimportar em memória com resultado
**idêntico byte a byte**. A cópia de teste do uniforme 001 também é idêntica.

`tools/uniform_texture.py` exporta PNG e aceita um PNG RGBA8 de 256×256 para
gerar uma **nova pasta sob `analysis/`**. Preserva cabeçalho e bytes finais,
recalcula CRC e recusa escrever na pasta original. Não ativa o save.

```sh
../deadpool-recomp/tools/.venv/bin/python tools/uniform_texture.py export \
  rpcs3/dev_hdd0/home/00000001/savedata/BLUS31029EUNIFORM001 \
  --png analysis/uniform001.png

../deadpool-recomp/tools/.venv/bin/python tools/uniform_texture.py stage \
  rpcs3/dev_hdd0/home/00000001/savedata/BLUS31029EUNIFORM001 \
  --png analysis/uniform001.png \
  --output-save analysis/staged/BLUS31029EUNIFORM001
```

Destinos devem ser novos. `ICON0.PNG` é a prévia antiga e fica preservada na
cópia; não confundir com os pixels reais de `DATA.BIN`. O recurso extraído é
uma imagem aplicada ao uniforme, não o atlas completo do jogador. Ainda falta
mapear cada save ao clube e ao uniforme titular/reserva/goleiro no EEDIT.
Nenhuma imagem de uniforme 2026 foi instalada. O teste de alteração visual
no jogo ainda está pendente.

## Texturas de maior resolução

O inventário em `analysis/visual-2026/installed_assets.json` registra 1.105
recursos: 389 uniformes, 343 faces, 354 elementos de estádio e 19 emblemas
de competição. Todos os CRCs conferem. As dimensões de `ICON0.PNG` são apenas
da prévia; não definem as dimensões do recurso. O formato dos demais tipos
ainda não foi decodificado.

O runtime compartilhado agora contém substituição por assinatura via `PS3_MODS`,
e o executável local contém `PS3_MODS_DUMP` (verificados em 05/11). Ainda falta
validar a substituição das camisas deste projeto no jogo. Colocar uma imagem 2K
no save de 256×256 não é uma solução validada.
Prioridades: identificar texturas estáticas de gramado/uniformes/faces,
substituição externa por assinatura, preservação de UV/alpha/mips, orçamento
de memória e comparação visual em partida. Não há pacote HD ativo.

### Captura isolada para identificar as camisas

Execute `zsh tools/capturar_camisas_2026.command` com o jogo fechado. Usa o perfil
Flamengo separado existente e desativa pacotes herdados do ambiente. Escolha o
Flamengo e visualize as camisas 1 e 2. O processo criado pela ferramenta é
encerrado após 180 segundos, ao observar 512 MiB gravados ou menos de 4 GiB
livres (verificação a cada 2 segundos, portanto não é quota rígida).
Não encerra processos anteriores e recusa iniciar se houver outro jogo aberto.

Saída: `analysis/visual-2026/runtime-captures/<data>/textures/`, com PNGs nomeados
pelas assinaturas reais e `textures.txt` do runtime; `boot.log` e `capture.json`
ficam no diretório acima. Para gerar a galeria de identificação:

```sh
../deadpool-recomp/tools/.venv/bin/python tools/index_texture_capture.py \
  analysis/visual-2026/runtime-captures/<data>/textures
```

A galeria ordena imagens 2:1 primeiro, mas não atribui clube ou função por
proporção. Após conferir a imagem original, será possível associar sua assinatura
à versão convertida. O runtime aplica o remapeamento de canais original também
à substituição; conferir isso e a orientação no modelo antes de aprovar o pack.
Preflight (`--check`) passou; captura interativa e substituição ainda pendentes.
Três testes do parser de índice passaram. Nenhum save original modificado.

## Referência PES 2021

### Conversão UV experimental — 05/11/2026

**Lote A/B concluído:** [galeria dos 80 atlas convertidos](../analysis/visual-2026/ab-kit-atlases/index.html),
slots p1/p2 dos 40 clubes, 1024×512. `tools/prepare_ab_kit_atlases.py` processa
sequencialmente e reutiliza resultados somente quando hashes da origem, mapa,
ferramentas e PNG coincidem. Retomada conferida sem nova conversão.
`tools/validate_ab_kit_atlases.py` validou a cobertura completa, hashes, dimensões,
CRCs e payload descompactado dos 80 PNGs. Quatro testes adicionais verificam o
validador, incluindo corrupção e truncamento; os três testes UV continuam passando.

Isso amplia a preparação de Flamengo para todos os clubes A/B, **não a cobertura
instalada no jogo**. O arquivo `visual-review.json` registra a amostra Palmeiras
p1: faixas vermelhas ao lado do tronco existem tanto na origem quanto na conversão;
a função dessas regiões precisa de conferência no modelo. Temporada e função
titular/reserva ainda não aprovadas para o lote. Nenhuma face ou camisa ativada.

`tools/extract_kit_uv_map.py` extraiu 7.305 pares de triângulos da tabela
`triangles_pes2013_1024x512.pkl` do conversor já baixado. O executável não foi
executado. A leitura restringe os objetos a dados numéricos locais e rejeita
outros imports; hash do pacote e tamanhos são verificados. Mapa JSON em
`analysis/visual-2026/kit-uv-map/`, origem 2048×2048 e destino 1024×512.

`tools/probe_kit_uv.py --club Flamengo --slot p1` (ou `p2`) gera duas alternativas
de orientação em `analysis/visual-2026/kit-uv-probes/club-08-p1/` e `club-08-p2/`.
A alternativa `uv-bottom-left.png` reorganiza visualmente a frente, costas,
mangas, calção e meias; a alternativa top-left apresenta partes trocadas e
invertidas. A primeira foi inspecionada, mas ainda não validada no modelo 3D.
São provas de formato com amostragem nearest e alpha original, não camisas
prontas: faltam acabamento de costuras, gola/braçadeira, mipmaps, associação ao
clube e caminho de substituição da textura completa no PS3. Não usar esse atlas
como imagem EUNIFORM de 256×256. Nenhum save alterado.

Três testes passaram em `tools/test_kit_uv.py`: identidade de pixels/alpha nas
duas orientações, triângulo degenerado e rejeição de import no leitor de dados.

O próprio autor publicou o [PES21 Kit Converter v3](https://foro.pesretro.net/showthread.php?mode=threaded&pid=486656&tid=13782),
com conversão de UV e saída para PES 2013. O pacote de 44,44 MB foi baixado
pelo link do autor e inspecionado: contém um executável Windows/PyInstaller
com Python 3.11. Não foi executado. Inventário e hash ficam em
`analysis/visual-2026/converter_inventory.json`; arquivo local também nessa
pasta. Não é uma ferramenta macOS pronta e sua saída não foi validada no PS3.

PES 2021 serve como referência de materiais, uniformes e aparências. Seus
modelos, esqueletos e atlas não foram demonstrados compatíveis com este port.
O conversor de kit completo também não substitui diretamente a imagem de
256×256 do Option File descrita acima.

## Validação

```sh
../deadpool-recomp/tools/.venv/bin/python -m unittest discover \
  -s tools -p 'test_*.py' -v
```

Os testes incluem os cinco filtros PNG, preservação de RGBA/alpha e metadados,
CRC, resolução incorreta e integridade dos elencos. Dados reais e downloads
ficam em `analysis/`, sem commit. Nenhum arquivo do runtime compartilhado foi
alterado por este trabalho de conteúdo.

## Prévias dos rostos existentes — 04/11/2026

`tools/face_preview.py` exporta 343 prévias de EFACE para pasta nova em analysis/.
Os saves têm 131.172 bytes e CRC válido. Hipótese visual: pixels 256×256 com
canais RGB nos bits 15–11, 10–6 e 5–1 de palavras big-endian, começando em +82.
Duas amostras foram inspecionadas visualmente; alpha, limite exato dos pixels,
metadados e vínculo com jogadores ainda não foram confirmados. A prévia usa
alpha opaco. Não há importador de faces nem face HD instalada.

Galeria: `analysis/visual-2026/face-previews/index.html`. Manifesto index.json
preserva hashes de origem. Todos os 343 PNGs passaram por validação de CRC e
tamanho ao decodificar. Não atribuir identidade a jogadores pela aparência.

## Pesquisa continental — 05/11/2026

- Baixados 13 arquivos da coleção River Plate 2025/26 para PES 2013 PC, com 26 BINs (face/cabelo). Conteúdo WESYS/zlib validado; DDS encontrados de 256 a 4096 pixels. Não implica resolução alta em todas as faces nem compatibilidade PS3.
- Fontes, hashes, nomes internos e propostas de correspondência ficam em `analysis/visual-2026/sources/continental/river-face-*.json`. Sete arquivos têm correspondência de nome nos elencos de referência; nenhuma identidade ou associação PES foi aprovada automaticamente.
- Kit Independiente Rivadavia baixado e PNGs pa/pb inspecionados (1024×512, CRCs válidos). **Reprovado como uniforme atual de 2026:** usa Lyon/Macro, enquanto a [camisa 2026 é AIFIT](https://tiendaazul.com.ar/productos/camiseta-oficial-1-2026-independiente-rivadavia-aifit/). Guardado apenas para referência de formato.
- Pacote Latinoamericano FL2026 v7 localizado; ambos os espelhos retornaram HTTP 403. Não conta como faces baixadas.
- Sem instalação no save de teste ou no perfil original. O relatório A/B anterior mantém seu escopo de 40 clubes; este material continental é separado.
