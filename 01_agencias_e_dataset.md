# 01 — Agências e dataset

> As features e o método desta página valem para qualquer agência. Os números são de **Bangkok** e devem ser recalculados com o kit de cada agência liberada.

## Como as agências funcionam

- Todo contrato é **ida e volta na mesma agência**. As agências são independentes: cada uma é um problema de otimização separado, com sua submissão.
- Haverá **6 agências pontuadas** + Bangkok (tutorial). Já listadas no portal: Bangkok, Istanbul, Hanoi. Os nomes são só identificadores.
- Cada agência vem com o mesmo formato de kit: `agencias.md`, `contratos_publicos.csv`, `frota_t0.csv` e o catálogo comum (`veiculos.csv`, `curvas/*.md`, `categorias.csv`, `carregadores.csv`, `entrada_eletrica.csv`).
- O que **muda entre agências**: vagas elétricas, tamanho e mix da frota, horário de funcionamento, entrada existente, volume e perfil dos contratos, e possivelmente os pesos da nota.
- O que é **comum**: catálogo de veículos, curvas, carregadores, entradas, regras do juiz, horário de ponta (seg–sex 18–21h).

### Features que devemos extrair de toda agência nova

Esta lista é a "ficha" que vai alimentar os modelos (ver doc 06):

| Grupo | Feature |
|---|---|
| Infra | vagas elétricas, kW útil da entrada existente, nível (B3/A4/SE) |
| Horário | horas abertas/semana, hora de fechamento nos dias úteis, abre durante a ponta?, horas entre 21h e a abertura, dias fechados, maior intervalo fechado (ex.: sáb 12h → seg 8h) |
| Frota | total e por categoria, % em contrato em T0, SOC médio de devolução dos que estão fora |
| Demanda | contratos/semana, mix por categoria, retiradas por dia da semana e por hora, % de devoluções na abertura |
| Energia | kWh/dia necessários (pelos km de devolução), kWh por categoria |
| Folga | máx. de carros fora ao mesmo tempo ÷ frota, por categoria |
| Pressão | kWh/dia ÷ (vagas × horas abertas), retiradas na 1ª hora após um longo fechamento |

## Bangkok — ficha

| Item | Valor |
|---|---|
| Vagas elétricas | 6 |
| Frota | 80 |
| Entrada existente | b3_45 (40,5 kW úteis) |
| Horário | Seg–Sex 08–18h, Sáb 08–12h, Dom fechado |
| Contratos públicos | 271 (4 semanas) |
| T0 | domingo 17/10/2049 18:00 (minuto 1080) |

Detalhe crítico do horário: a agência **fecha às 18h, exatamente quando começa a ponta**. E fica fechada de **sábado 12h até segunda 8h (44 h)**.

## Contratos (`contratos_publicos.csv`)

Colunas: `id`, `categoria` pedida, `retirada`, `devolucao`, `autonomia_min_retirada_km`, `km_devolucao` (autonomia restante na volta). Sem valores ausentes.

### Volume e estabilidade

| Semana | Bronze | Prata | Ouro | Diamante | Total |
|---|---:|---:|---:|---:|---:|
| 1 | 27 | 11 | 24 | 6 | 68 |
| 2 | 22 | 20 | 19 | 7 | 68 |
| 3 | 23 | 17 | 20 | 4 | 64 |
| 4 | 33 | 17 | 14 | 7 | 71 |

Volume estável (~68/semana), mas o mix varia bastante semana a semana (Ouro de 14 a 24, Prata de 11 a 20). Isso indica que as semanas ocultas devem ter volume parecido com mix diferente: **a escolha precisa ser robusta ao mix**.

Total por categoria: Bronze 105 (39%), Ouro 77 (28%), Prata 65 (24%), Diamante 24 (9%).

### Quando os clientes retiram

Retiradas médias por dia da semana: Seg **21,2**, Ter 9,2, Qua 11,2, Qui 8,8, Sex 11,5, Sáb 5,8, Dom 0.

Retiradas por hora (total das 4 semanas):

| 8h | 9h | 10h | 11h | 12h | 13h | 14h | 15h | 16h | 17h |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **59** | 34 | 22 | 25 | 20 | 12 | 9 | 24 | 27 | 39 |

Dois picos: abertura (8–9h) e fim do dia (16–17h). A segunda-feira tem o dobro de retiradas dos outros dias. Todas as retiradas são em horário de funcionamento.

### Quando os carros voltam

- **172 de 271 devoluções (63%) acontecem às 8h**, com mediana às 8:08. É o padrão "devolve ao abrir".
- Devoluções médias por dia: Seg 12,2, Ter 8,2, Qua–Sex 8,8, Sáb 6,2.
- Nenhuma devolução fora do horário de funcionamento.
- 59 contratos têm devolução **depois** da janela pública (contratos longos, até ~42 dias). O juiz simula o horizonte completo, então isso afeta o estado da frota no fim da janela e no começo das semanas ocultas.

### Duração

Mediana 86 h (~3,6 dias), média 142 h, mínimo 7,7 h, máximo ~1.000 h. Distribuição de cauda longa (lognormal-like). Parecida entre categorias.

### Energia que volta para carregar

O SOC de devolução é `km_devolucao ÷ autonomia do modelo que atendeu × 100` (teto: o SOC de saída). Estimando com a média dos modelos de cada categoria:

| Categoria | SOC médio na volta | kWh médio para voltar a 80% |
|---|---:|---:|
| Bronze | 39% | 11,9 |
| Prata | 36% | 17,0 |
| Ouro | 38% | 18,3 |
| Diamante | 24% | 32,7 |

**Nenhum contrato volta com ≥ 80%**: toda devolução entra na fila. Energia total das devoluções dentro da janela: **~3.550 kWh em 28 dias ≈ 127 kWh/dia**.

Observação: o mesmo km de devolução dá SOCs muito diferentes por modelo (Leapmotor 288 km vs. Dolphin Plus 427 km de autonomia). Qual carro atendeu importa, mas isso é decidido pela regra fixa de escolha, não pela equipe.

### Ponto de atenção: `autonomia_min_retirada_km`

A coluna é carregada pelo `dados.py` mas **não aparece em nenhuma regra do regulamento** (o critério é só SOC ≥ 80%). Em 43 contratos, ela é maior que 80% da autonomia do modelo de menor alcance da categoria. Hipótese: não é usada pelo juiz. Confirmar com o `comparar.py` quando o motor estiver pronto; se o motor bater com o juiz ignorando-a, está resolvido.

## Frota em T0 (`frota_t0.csv`)

| Categoria | Modelos | Total | Em contrato | Estoque pronto |
|---|---|---:|---:|---:|
| Bronze | Kwid 14, JAC 18 | 32 | 24 | 8 |
| Prata | Geely 10, Dolphin Mini 10 | 20 | 18 | 2 |
| Ouro | MG4 11, Dolphin GS 10 | 21 | 11 | 10 |
| Diamante | Dolphin Plus 3, Leapmotor 4 | 7 | 5 | 2 |
| **Total** | | **80** | **58** | **22** |

- Todo o estoque pronto está em exatamente 80%. Nenhum carro em `estoque_a_carregar`.
- Os 58 em contrato voltam com SOC médio de 35% (mín. 4%, máx. 75%), todos abaixo de 80%.
- **22 deles voltam na segunda 18/10** (a maioria às 8h), mesmo dia com 22 retiradas. O primeiro dia já é um teste de estresse.

## Folga da frota

Máximo de carros fora ao mesmo tempo, por categoria pedida, na janela pública:

| Categoria | Máx. fora | Frota | Folga |
|---|---:|---:|---:|
| Bronze | 29 | 32 | 3 |
| Prata | 19 | 20 | 1 |
| Ouro | 18 | 21 | 3 |
| Diamante | **7** | **7** | **0** |
| Total | 66 | 80 | 14 |

A frota é apertada. Diamante não tem folga nenhuma e não pode receber upgrade (é a categoria mais alta). Prata depende de upgrade para Ouro/Diamante nos picos.

### Teste de sensibilidade (estoque com atraso fixo)

Simulação simplificada: cada carro devolvido fica pronto X horas depois (ignorando vagas e horário). Resultado:

| Atraso | Perdidos | Upgrades |
|---|---:|---:|
| 0–6 h | 0 | 0 |
| 8 h | 2 (Diamante) | 0 |
| 12 h | 2 (Diamante) | 4 |
| 24 h | 4 (Diamante) | 7 |

Leitura: se cada carro ficasse pronto em até ~6 h, ninguém seria perdido. Como recarga AC leva 2–5 h e DC 25–75 min, a energia não é o problema; o risco vem da fila (6 vagas, plugar só aberta, carro a 80% segura a vaga à noite).

**Resultado do motor (depois desta análise):** em Bangkok, uma única saída DC-30 já atende 100% dos contratos, e 3× AC-7 perde só 1–2. Bangkok é uma agência folgada; a decisão ali será de custo. As agências pontuadas provavelmente serão mais apertadas, e a mesma análise deve ser refeita para cada uma.

## Pontos de pressão a procurar em qualquer agência

1. A primeira hora após um fechamento longo (em Bangkok, segunda 8–10h, após sáb 12h → seg 8h).
2. Noites: só `vagas` carros carregam por noite.
3. A categoria mais alta com folga ≤ 1 (em Bangkok, Diamante com folga 0).
4. Dias com retiradas muito acima das devoluções (em Bangkok, segunda: 21 retiradas vs. 12 devoluções em média).

Em Bangkok, nenhum desses pontos chega a causar perdas com infraestrutura mínima razoável (ver doc 04). Em agências maiores, são os primeiros lugares onde olhar as séries de fila e clientes perdidos.
