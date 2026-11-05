# Narração PT-BR — 04/11/2026

Ainda não foi instalada a narração do PES 2020 nem validada sincronização em
partida. O pacote atual permanece intacto.

## Fonte PES 2020

[SmokePatch](https://www.pessmokepatch.com/2019/09/2020coms.html) lista Milton
Leite e Mauro Beting. Seu link é https://link-to.net/13243/sp20Brazil.
A consulta chegou à página Linkvertise, mas não revelou o arquivo para download.
O pacote NÃO foi baixado. A fonte oferece arquivos para a pasta DATA do PES 2020
PC, sem comprovar compatibilidade com PES 2013 PS3.

## Pacote atual medido

Origem somente leitura: `/Users/erik-martins/mnt_pes13/PS3_GAME/USRDIR/dt00_b.img`.

- AFS de 549.289.984 bytes, 12.140 slots, um vazio.
- 12.139 entradas identificadas como ADX mono de 24.000 Hz.
- Identificadores AINF como `B_VP_T0_R0005`, ainda sem associação aos lances.
- Catálogo: `analysis/narration-2026/current-ptbr/inventory.json`.
- Cinco amostras extraídas (slots 1, 2, 3, 100, 1000), decodificadas com FFmpeg
  sem erro. Slot 1 também em WAV. Isso não comprova sincronização em partida.

Ferramenta: `tools/commentary_inventory.py ARCHIVE --output analysis/PASTA_NOVA
--sample-slots 1 2 3`, usando o Python compartilhado do Deadpool. Só permite
saída em pasta nova dentro de analysis; não modifica o arquivo de origem.
Tabela completa validada e três casos malformados rejeitados (assinatura,
tamanho da tabela e limites das entradas).

## Trabalho pendente

1. Obter e inventariar o pacote PES 2020.
2. Associar falas aos eventos por escuta e observação dos disparos do PES 2013.
   Slots com o mesmo número em versões diferentes não comprovam equivalência.
3. Converter e preparar substituições em cópia separada, preservando slots e
   parâmetros esperados pelo PES 2013. Manter falas atuais sem equivalente.
4. Testar gols, faltas, escanteios, substituições, intervalo e nomes de jogadores
   em partida; medir atraso e sobreposição antes de ativar a substituição.

Há registro anterior de falha CoreAudio -66681 em O_QUE_FALTA.md. Não foi
revalidado nesta investigação e nenhum serviço de áudio foi reiniciado.
A narração atual não contém necessariamente os nomes dos atletas de 2026.

## Teste isolado de saída — 04/11/2026

Executado o binário existente (sem recompilar) com AUDIO_RATE e AUDIO_PEAK,
saves/cache HDD1 isolados em analysis/narration-2026/audio-probe. Limite de
35 segundos, seguido de encerramento apenas do PID iniciado pelo teste.
O processo não respondeu ao término em cinco segundos e foi encerrado com kill.
Resultado -9 é desse encerramento, não evidência de crash espontâneo.

Log: primeira janela 188,1 blocos/s, seguintes 187,5, descarte registrado zero.
Picos impressos foram 0,0000, embora o contador de amostras não exatamente zero
indique atividade; isso não comprova som audível. O campo device buf 0 não mede
latência SDL. O teste ficou na inicialização, não em lances de uma partida.
Não medimos sincronização ponta a ponta e não alteramos temporização, buffer ou
velocidade das falas. O próximo teste precisa correlacionar imagem e áudio de
uma partida; não há correção de sincronização validada neste momento.
