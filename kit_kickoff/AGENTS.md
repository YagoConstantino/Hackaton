# AGENTS.md (kit de kickoff)

## Objetivo
Completar `kickoff/motor.py` para reproduzir o juiz (regulamento) na janela pública. Python 3.10+, só biblioteca padrão.

## Regras de trabalho
- NÃO alterar `kickoff/dados.py`, `validar.py`, `potencia.py`, `medicao.py`, `nota.py`, `tempo.py`, `modelo.py` (já batem com o juiz), salvo pedido explícito do humano.
- Implementar UM TODO/etapa por vez, na ordem das etapas. Não implementar etapas futuras.
- Só biblioteca padrão. Sem dependências novas.
- NÃO ler `dados/*/*.csv` inteiros no contexto (grandes). Resumo: `python -m kickoff.dados <Agencia>`.
- Após cada mudança: `python -m unittest discover -s testes` e `python simular.py exemplo_submissao.json`.
- Escrever um teste por etapa em `testes/` com os exemplos numéricos abaixo.
- NUNCA chamar a API paga (`kickoff.api teste`) sem aprovação do humano: gasta m7Coins (placar 20, completo 50). Bangkok é grátis (0 m7Coins, cooldown 1 min).
- Mudança mínima: só o que a etapa pede. Não refatorar o laço de eventos.

## Mapa do motor (`kickoff/motor.py`)
Pronto (não mexer): `agendar`, `rodar`, `_agendar_inicio`, `avancar`, `anotar`, `plugar`, `desplugar`, `sair_do_patio`, `violar`, `checar_ocupacao`, `on_retirada`.

TODO (um `# TODO(etapa N)` em cada):

| Etapa | Método | Seção | Faz |
|---|---|---|---|
| 2 | `soc_devolucao` | 4.1 | SOC = km/autonomia_km*100, teto = `v.soc` |
| 2 | `entrar_patio` | 5.2 | SOC<80 -> fila (`entrou_fila_t`); senão apto; depois `plugar_fila` + `recalcular_potencias` |
| 2 | `escolher_carro` | 5.1, 6.3.1 | elegível e ordem de escolha; None = cliente perdido |
| 2 | `on_devolucao` | 5.1 | já seta SOC e chama `entrar_patio`; conferir |
| 3 | `ordenar_fila` | 6.3.3 | `chegada`, `menor_soc` (km) |
| 3 | `escolher_ponto` | 6.3.4 | ponto com mais potência para o carro |
| 3 | `plugar_fila` | 5.2, 6.3.3 | só aberta, na ordem, enquanto houver saída |
| 3 | `recalcular_potencias` | 5.3, 6.3.5 | camada 1 (carregador) |
| 3 | `agendar_fim_degrau` | 5.3, 6.3.2 | agenda `fim_recarga` no próximo degrau/alvo |
| 3 | `on_fim_recarga` | 5.2 | alvo: desplugar se aberta, senão segura saída; replugar fila |
| 4 | `recalcular_potencias` | 5.3, 6.3.5, 6.3.7 | camada 2: `self.limite_kw` + `divisao` |
| 5 | `on_abertura`, `on_fechamento` | 5.2 | desplugar parados no alvo ao abrir; fechada não pluga/desplug |
| 5 | `on_ponta` | 5.3, 6.3.6 | com `evitar_ponta`: 0 kW, segue plugado |
| 6 | `ordenar_fila` | 6.3.3 | `proxima_retirada` e `menor_soc` completos |
| 7 | `agendar_eventos`, `on_evento` | 11 | eventos ao vivo |

Detalhes e exemplos de cada método estão na docstring dele. Ler só o método da etapa atual.

Estado útil: `self.patio` (id->Veiculo), `self.fila`, `self.pontos` (ordenados por id), `self.aberta`, `self.em_ponta`, `self.pol` (política), `self.limite_kw`, `self.contratos`. `Veiculo.token`: incrementar invalida `fim_recarga` agendado.

## Regras essenciais (não errar)
- SOC alvo fixo 80%; só entrega com SOC >= 80% (5.1).
- Escolha do carro: categoria >= pedida (upgrade sim, downgrade nunca) -> menor upgrade -> menor SOC -> não plugado -> menor `id` alfabético (5.1, 6.3.1).
- Sem carro apto: cliente perdido, sem espera (5.1).
- Devolução vem em km: SOC = km/autonomia do modelo que atendeu*100, nunca acima do SOC de saída (4.1).
- Mesmo minuto: devolução -> abertura/ponta/eventos -> fim de recarga -> retirada -> fechamento (5.1; constantes `PRIO_*`).
- Plugar/desplugar só com a agência aberta; a recarga continua fechada; carro em 80% fechado segura a saída até abrir (5.2).
- Retirado plugado: desplugado na hora (5.1).
- Fila: devolução abaixo de 80%; reordenar e tentar plugar quando volta carro, termina recarga, agência abre, carregador volta (5.2, 6.3.3).
- Plugados <= saídas instaladas <= vagas (5.2).
- `menor_soc`: menor km restante (`autonomia_km*soc/100`), não SOC. `chegada`: FIFO (carros da fila em T0 entram no mesmo instante). `proxima_retirada`: primeiro contrato não retirado com categoria <= a do carro; sem reserva vai ao fim; empate maior SOC. Último desempate sempre menor `id` (6.3.3).
- Escolha do carregador: em operação, com saída livre, maior potência estimada (nominal dividida igualmente com quem já está, cada um limitado pela curva), ignorando limite e `divisao`; empate: primeiro de `self.pontos`; não troca de carregador depois (6.3.4).
- Potência em duas camadas: (1) nominal do carregador entre carros que ainda carregam, teto na curva; (2) limite da agência reparte o que veio da camada 1. `igual` -> `potencia.enchimento_agua`; `prioridade` -> `potencia.sequencial` na ordem da prioridade. Recalcular a cada mudança (5.3, 6.3.5).
- Curva em degraus de 5%: índice `min(19, floor(soc/5))`; `potencia.potencia_curva` já faz (e a média de duas linhas já vem pronta em `dados.py`) (5.3).
- Limite da agência: B3 = kW útil da entrada; A4/SE = demanda contratada (`self.limite_kw`), teto rígido (5.3, 6.3.7).
- Ponta seg-sex 18:00-21:00; com `evitar_ponta`: 0 kW, continua plugado, plugar permitido (5.3, 6.3.6).
- Medição em janelas de 15 min (`Medidor`, já pronto) (5.3).
- Desempate final em toda ordenação: menor `id` (5.1).

Exemplos para testes (valores do regulamento):
- 6.3.2: Dolphin GS (44,9 kWh) 20%->80% sozinho em DC-60: 36,7 min.
- 6.3.3: A(Bronze 30%), B(Prata 20%), C(Ouro 55%), D(Diamante 40%): menor_soc A,B,D,C; chegada A,B,C,D; proxima_retirada C,D,B,A.
- 6.3.5 (limite 40,5): `igual` 10,125 para cada; `prioridade` Kwid 26,6, Geely 13,9, JAC 0, Dolphin 0. Limite 80: `igual` 21,1833 (JAC 16,45); `prioridade` Kwid 26,6, Geely 53,4.

## Unidades e convenções
- Tempo: minutos desde 17/10/2049 00:00 (domingo). T0 = 1080. Dia = 1440. Janela pública = `tempo.JANELA_PUBLICA`.
- `tempo.dia_semana(t)`: Python, seg=0 ... dom=6. Ponta: `tempo.eh_ponta(t)`. Aberta: `tempo.aberta(agencia, t)`.
- SOC em %, potência em kW, energia em kWh, autonomia em km. Degrau = 5% de SOC.
- Depurar: `tempo.texto(t)` (ex.: `Seg 18/10 07:30`).
- Submissão normalizada (`sub`): `carregadores` {modelo_id: qtd}, `entrada`, `demanda_contratada_kw` (None em B3), `politica` {prioridade, evitar_ponta, divisao}.

## Como validar contra o juiz
1. `python -m kickoff.api teste Bangkok sub.json --completo --salvar resp.json` (Bangkok grátis; exige `GAMEDAY_URL`, `GAMEDAY_TOKEN`; só com OK do humano).
2. `python comparar.py sub.json resp.json` (opcional `--eventos arq.json`).
3. Ler "DIVERGE em": a primeira janela divergente em `series.*@<hora>` indica onde o motor errou. Corrigir a regra daquele instante, repetir. Meta: `OK: bate com o juiz` para várias políticas.

## Prompt sugerido (o humano cola)
```
Leia AGENTS.md. Implemente a etapa N do roteiro em kickoff/motor.py: só os métodos com
# TODO(etapa N), seguindo as docstrings e as seções do regulamento citadas. Não altere
dados.py, validar.py, potencia.py, medicao.py, nota.py, tempo.py, modelo.py. Escreva um
teste em testes/ com os exemplos numéricos da etapa. Rode `python -m unittest discover -s testes`
e `python simular.py exemplo_submissao.json`. Não chame a API paga. Resuma o que mudou em 5 linhas.
```
