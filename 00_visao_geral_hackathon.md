# 00 — Visão geral do hackathon

## O jogo em uma frase

Cada equipe projeta e opera a recarga de uma rede de agências de aluguel de carros elétricos. Para cada agência, escolhe **carregadores**, **entrada elétrica**, **demanda contratada** e **política de recarga**. Um juiz (simulador oficial) roda 4 semanas de operação com essas escolhas e devolve uma nota.

## O que a equipe decide (uma submissão JSON por agência)

```json
{
  "agencia": "Bangkok",
  "carregadores": {"dc_60x2": 1, "ac_7": 2},
  "entrada": "a4_150",
  "demanda_contratada_kw": 60,
  "politica": {"prioridade": "proxima_retirada", "evitar_ponta": false, "divisao": "prioridade"}
}
```

| Decisão | Opções | Observação |
|---|---|---|
| `carregadores` | quantidades de 6 modelos (ac_7, ac_11, ac_22x2, dc_30, dc_60x2, dc_120x2) | Σ saídas ≤ vagas elétricas; ao menos 1 carregador |
| `entrada` | 10 níveis, de b3_45 a se_2000 | só manter ou subir; b3_45 não pode ser "comprado" |
| `demanda_contratada_kw` | 30 até o teto da entrada, passo 10 | só em A4/SE; omitir = teto (e paga pelo teto) |
| `prioridade` | menor_soc, chegada, proxima_retirada | ordem da fila de recarga |
| `divisao` | igual, prioridade | como o limite de potência é repartido |
| `evitar_ponta` | true, false | não carregar seg–sex 18h–21h |

O **SOC alvo é fixo em 80%** e não é decisão.

## Pontuação (uma moeda só: pontos)

```
nota = w_certo·certos + w_up·upgrades − w_nao·não_atendidos
       − w_dem·demanda_kW − w_ponta·kWh_na_ponta − w_obra·custo_de_obra
```

A hierarquia declarada é: **atender o cliente → entregar a categoria certa → gastar pouca infraestrutura e potência**. Portanto, em ordem esperada de grandeza: `w_nao` grande, `w_certo > w_up > 0`, e os custos menores por unidade, mas que somam.

Pontos importantes da nota:

- Custo de obra e demanda **entram inteiros em cada janela avaliada**. Um carregador a mais só vale se evitar perdas suficientes para pagar a obra.
- Ampliar a entrada custa o **valor cheio do novo nível**, sem crédito pela existente. Manter custa 0.
- **B3 não paga demanda contratada.** Isso torna o b3_75 potencialmente mais barato que um A4 com demanda baixa (depende dos custos revelados em H4).
- Pico de 15 min, energia total e % atendimento são informados mas **não pontuam**.
- A organização pode **mudar os pesos de uma agência durante o dia**, inclusive para envios já feitos. Os valores vigentes ficam em `GET /catalogo` (pesos) após H4.

## Nota final

Soma das notas das **6 agências pontuadas**, avaliadas nas **semanas ocultas** (4 semanas depois do período público, nunca entregues). Bangkok é tutorial e não pontua. Agência sem envio final vale 0, e agências maiores pesam mais (volume de contratos).

Desempate: menos não atendidos nas ocultas → menor custo de obra → envio final mais cedo.

**Consequência:** o que importa é generalizar. Ajustar fino ao público é perigoso; a escolha deve ser robusta a variações de demanda.

## Cronograma (12 h)

| Momento | O que acontece |
|---|---|
| H−1 a H0 | Abertura, tutorial em Bangkok, PalavraChave |
| H0 a H4 | **Neblina**: pesos e custos de obra ocultos. Testes devolvem só nota + métricas físicas |
| H4 | Revelação: anexo com pesos e custos. Testes passam a trazer a cascata de pontos |
| H4 a H7:30 | **Clara** |
| H7:30 | Congelamento: fim de testes e envios |
| H8 a H11 | Apresentações (12 min + 5 min perguntas) |

As 6 agências são liberadas aos poucos; **algumas só na segunda metade**. Já apareceram no portal: Bangkok, Istanbul e Hanoi.

## Economia de m7Coins (1.000 por equipe)

| Ação | Custo | Cooldown |
|---|---|---|
| Teste "placar" | 20 | 5 min por agência |
| Teste "completo" (com séries de 15 min) | 50 (30 se já pagou o placar) | 5 min |
| Teste idêntico a um já feito | 0 | — |
| 1º envio final por agência | 0 | — |
| Reenvio final | 80, 160, 320… (dobra) | 15 min |
| **Testes em Bangkok** | **0** | 1 min |

1.000 m7Coins ≈ 50 testes placar ou 20 completos para **6 agências**. Ou seja, ~8 placar por agência. Sem simulador próprio, não dá para explorar. Reserve saldo para as agências que abrem tarde e para reagir a eventos.

## Neblina × Clara: o dilema

Na Neblina os testes devolvem a nota (calculada com pesos ocultos), mas não a cascata. A equipe pode **inferir os pesos** comparando notas de variações. Como a nota é linear nas métricas, isso é um problema de regressão linear (detalhes em `06_analise_para_machine_learning.md`). Bangkok é grátis, então a inferência pode ser feita sem gastar nada — desde que os pesos de Bangkok sejam representativos (a organização pode ter pesos por agência; os custos de obra devem ser do catálogo, iguais para todas).

## Eventos ao vivo

Podem surgir a qualquer momento: limitação da concessionária, carregador quebrado etc. Valem para todos, aparecem também nas semanas públicas (para dar para testar), e os envios finais já feitos são **reavaliados automaticamente**. Reagir custa reenvio normal. Após um evento, testes "idênticos" voltam a ser cobrados.

Implicação: uma submissão com **folga** (ex.: um carregador a mais, ou não depender de um único DC) pode sobreviver a um evento sem reenvio.

## Entregáveis e prêmios

Dashboard obrigatório por agência: cascata de pontos (modelo próprio vs. juiz), curva de potência 15 min contra o limite e a ponta, ocupação de vagas e fila, SOC na retirada, clientes perdidos por dia/hora. No consolidado: m7Coins gastos, custo de obra, evolução da nota, justificativa da entrada/demanda.

Prêmios especiais que se conectam diretamente ao trabalho de modelagem:

- **Melhor modelagem**: menor erro do modelo próprio contra o juiz, com menos m7Coins.
- **Melhor leitura da Neblina**: inferência dos pesos mais próxima dos reais.
- **Melhor engenharia elétrica**: racional de entrada, demanda e ponta.
- **Melhor dashboard**.

## Estratégia geral recomendada

1. Completar o motor (`motor.py`) e validar contra o juiz em Bangkok (grátis) até `OK: bate com o juiz` em várias políticas.
2. Inferir pesos e custos na Neblina via testes desenhados em Bangkok.
3. Para cada agência liberada: extrair features, simular localmente um grande número de configurações em cenários perturbados, escolher a mais robusta.
4. Gastar m7Coins só para confirmar a escolha final de cada agência (1–2 testes) e fazer o 1º envio final cedo (é grátis). Reenviar só se a revelação de H4 mudar muito a decisão.
5. Manter folga de saldo para eventos e agências tardias.
