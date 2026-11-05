# Save experimental — Flamengo 2026

Criado em `analysis/test-save-flamengo-2026/`, separado do perfil principal.
Para abrir, feche uma eventual partida em execução e execute:

```sh
zsh tools/testar_flamengo_2026.command
```

Também pode abrir `tools/testar_flamengo_2026.command` pelo Finder. O disco
precisa estar montado e a árvore VFS já preparada pelo launcher habitual.

## O que este teste contém

- Flamengo doméstico: 27 nomes e números da referência coletada de 2026.
- Cópia das opções e de todos os saves visuais existentes, incluindo 343 faces.
- Manifesto com jogadores substituídos, fontes e hashes de antes/depois.

**Não é uma atualização completa de 2026.** Faces, idades, posições, atributos,
uniformes e escalação continuam herdados do save antigo. Os jogadores foram
renomeados sobre os IDs existentes: seleções ou variantes continentais que
referenciem esses IDs podem mostrar os mesmos nomes de teste. Não usar este
perfil para iniciar uma Master League definitiva. Os outros clubes não foram
atualizados. Nenhuma face HD ou nova narração foi instalada.

## O que conferir dentro do jogo

1. Em Editar/Times, selecionar CR Flamengo e conferir os 27 nomes e números.
2. Abrir a aparência de alguns jogadores: as faces ainda são as antigas.
3. Entrar em um amistoso, conferir escalação e observar carregamento/renderização.
4. Salvar, sair e reabrir pelo mesmo launcher para testar persistência.

O launcher aponta saves e cache HDD1 para o perfil de teste. Abrir pelo launcher
habitual volta ao perfil original. Não copie os arquivos por cima dos originais.

## Validação realizada

CRC do EEDIT recalculado e conferido pelo leitor; os 27 nomes/números conferidos;
IDs e quantidade de jogadores preservados. Alterações limitadas aos campos de
nome, nome na camisa, número no elenco e CRC. Originais e recursos visuais
conferidos por hash. Ainda não validado carregando o jogo com este save.

Pacote destinado ao port local: PARAM.PFD foi copiado sem reassinatura; não é
um save preparado para importação em um PS3 físico.

Gerador: `tools/create_test_save.py`. Recusa sobrescrever um perfil de teste já
existente para não perder os testes feitos pelo usuário.

## Retorno do teste em janela

O usuário mostrou a tela pré-partida Flamengo x Fluminense com os nomes novos
visíveis. Isso valida o carregamento até a escalação, não a partida completa.
Em seguida relatou aparente travamento. Amostra de três segundos do PID 23553,
às 23:55 de 04/11/2026: processo ativo (~141% CPU), janela processando eventos;
thread PPU principal em func_00DB1C84, predominantemente sys_timer_usleep.
Ainda não distingue espera normal de travamento. Causa e relação com o save
não demonstradas. Pilhas em diagnostics/sample-23553.txt no perfil de teste.
Nenhum processo do usuário foi encerrado.

O usuário confirmou que a partida começou antes de congelarem imagem e jogadores.
Uma segunda amostra do mesmo processo manteve a thread principal em
func_00DB1C84 (156/158 amostras no mesmo sleep). O código dessa função espera
que a diferença entre contadores em 0x01BF74C0/0x01BF74C4 fique menor que dois,
e depois chama cellGcmSetPrepareFlip (NID 0x0B4B62D5 confirmado na tabela HLE
gerada). Há dois loops de espera nessa função: somente as pilhas não distinguem
qual condição ficou presa. Outras threads PPU/SPU continuam executando.
Isso orienta investigar conclusão/apresentação de quadros; não confirma a causa
nem exclui problemas de dados. Save carregado e início de partida confirmados
pelo usuário; partida completa e estabilidade continuam pendentes.
