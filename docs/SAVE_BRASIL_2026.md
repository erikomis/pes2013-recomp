# Perfil experimental Brasil 2026

Criado em `analysis/test-save-brasil-2026/`, separado do original e do teste
anterior do Flamengo. Abrir com o jogo fechado:

```sh
zsh tools/testar_brasil_2026.command
```

O disco precisa estar montado e a VFS preparada. Este comando não usa os pacotes
de texturas herdados do ambiente. Salvamentos ficam somente neste perfil.

## Aplicado

- 716 nomes e números nas listas de 27 clubes com slot doméstico identificado.
- Até 32 profissionais por clube, usando registros com clube atual confirmado
  na coleta CBF e evidência de partidas. Recorte de referência: 04/11/2026.
- Slots excedentes de jogadores dos próprios clubes-alvo foram reutilizados
  quando outro clube precisava de mais registros. Nenhum ID novo foi criado.
- As listas foram escritas no EEDIT, não apenas exportadas em JSON.

## Limitações deste teste

**Não é uma atualização completa de jogadores.** IDs antigos foram reutilizados;
posições, idade, atributos, nacionalidade, rosto/cabelo e nome falado continuam
herdados. A ordem usa um goleiro primeiro e prioriza titulares da referência,
mas a formação e as posições do jogo não foram ajustadas. Não usar para Master
League definitiva. IDs também presentes em seleções ou outros elencos transmitem
os novos nomes a esses elencos; o manifesto lista as referências conhecidas.

As propostas ESPN de identidade/posição não foram aplicadas. Números repetidos
na fonte de Atlético Goianiense e Ponte Preta foram preservados e sinalizados
no manifesto, sem inventar substitutos. Felipe Vizeu (Avaí) foi excluído desta
aplicação porque a entrada não tinha confirmação do clube atual.

13 clubes continuam pendentes de slot: Mirassol, Remo, Athletic, Botafogo-SP,
CRB, Cuiabá, Fortaleza, Novorizontino, Juventude, Londrina, Operário-PR,
São Bernardo e Vila Nova. Ligas não foram reorganizadas. Rostos e uniformes
baixados/convertidos ainda não foram instalados; os recursos antigos foram copiados.

## Verificado

CRC, releitura dos 716 nomes/números/listas, IDs e layout preservados,
alterações restritas aos campos conhecidos, 3.322 arquivos de apoio copiados
conferidos por hash e EEDIT original inalterado. Carregamento e partida deste
perfil ainda não testados. PARAM.PFD não reassinado: pacote destinado ao port
local, não à importação em PS3 físico.

`manifest.json` contém hashes de origem, fontes e alterações por clube/jogador;
`validation.json` contém os resultados. Gerador: `tools/create_brazil_test_save.py`,
que recusa sobrescrever um perfil existente.
