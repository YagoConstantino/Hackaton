# 04 — Carregadores, entrada elétrica e horário de ponta

> **Vale para qualquer agência.** `carregadores.csv` e `entrada_eletrica.csv` vêm em cada kit e são lidos por agência; vagas, entrada existente e horário vêm do `agencias.md` de cada uma. As regras abaixo são fixas; os números de capacidade são calculados por fórmula e exemplificados com Bangkok no fim.

## Carregadores

`carregadores.csv`: `modelo_id`, `modelo`, `tipo` (AC/DC), `potencia_kw`, `saidas`.

Regras fixas:

- **Σ saídas ≤ vagas elétricas** da agência (carregador de 2 saídas conta 2). Pelo menos 1 carregador.
- Em carregador de 2 saídas, a potência nominal é repartida entre os carros que ainda carregam (pela `divisao`), com teto na curva de cada um; a sobra de um vai para o outro.
- O carro escolhe o carregador que lhe daria **mais potência estimada**, ignorando o limite e a `divisao`. Empate: ordem alfabética do id. **Não troca** depois de plugado.
- Custos em pontos só saem em H4.

Como avaliar cada modelo de carregador numa agência:

| Pergunta | Como responder |
|---|---|
| AC acima de 7 kW ajuda? | só para modelos da frota com curva AC > 7,4 kW |
| Carregador AC de 2 saídas divide de fato? | só se a soma dos AC máximos de 2 carros passar da nominal |
| DC rápido ajuda? | só para modelos com DC útil acima da parte que o carregador entrega, **e** se o limite da agência deixar passar |
| 2 saídas vale mais que 1? | compara custo por saída (H4) com a perda de potência quando os dois carregam juntos |

### Espaço de busca de carregadores (catálogo de 6 modelos)

| Vagas | Combinações válidas |
|---:|---:|
| 4 | 70 |
| 6 | 258 |
| 8 | 741 |
| 10 | 1.805 |
| 12 | 3.905 |
| 16 | 14.222 |
| 20 | 41.040 |

× 12 políticas × opções de entrada/demanda. Com o motor a ~0,1 s por rodada, até ~10 vagas dá para enumerar tudo; acima disso, poda e modelo substituto (doc 06).

## Entrada elétrica

`entrada_eletrica.csv`: `nivel_id`, `descricao`, `kva`, `kw_util`. kW útil = kVA × 1,0 × 0,9.

Regras fixas:

- **Limite da agência** (teto rígido): em B3 (≤ 75 kVA) é o kW útil; em A4/SE é a **demanda contratada**.
- Só manter ou subir. Subir custa o **valor cheio** do novo nível; manter custa 0.
- B3 de 45 kVA só vale como existente; quem tem b3_45 pode subir para b3_75.
- **B3 não paga demanda.** A4/SE pagam por kW contratado, em cada janela.
- Demanda: 30 até `floor(kW_útil/10)×10` (máx. 2000), passos de 10, o juiz arredonda (5 sobe). **Omitida = paga o teto.** Sempre enviar explicitamente.

Regra de decisão: ampliar só vale se o limite atual **corta potência em momentos que causam cliente perdido ou upgrade**. Corte à noite não custa nada.

## Horário de ponta

Fixo: seg–sex 18:00–21:00. Energia nesse intervalo desconta por kWh. Com `evitar_ponta = true`, todos a 0 kW na ponta, continuam plugados, plugar continua permitido.

### Regra para `evitar_ponta` em qualquer agência

`evitar_ponta = true` é **dominante** (mesmos clientes, zero energia na ponta) quando:

1. a agência **fecha até as 18h** em todos os dias úteis (ninguém retira nem pluga durante ou logo após a ponta), e
2. o tempo de 21h até a próxima abertura basta para todos os carros plugados chegarem a 80% dentro do limite:
   `horas(21h → abertura) ≥ max_carros( kWh_restante ÷ min(P_carregador, curva, L ÷ nº_plugados) )`.

Se a agência fica aberta durante a ponta (fecha 20h, 22h, 24h) ou abre muito cedo, há troca real: simular as duas opções.

## Fórmulas de capacidade (para qualquer agência)

Notação: `V` vagas, `L` limite (kW), `H_d` horas abertas no dia, `E` kWh/dia necessários (soma de `(80 − SOC_volta) × bateria` das devoluções), `t̄` tempo médio de recarga no carregador escolhido.

| Indicador | Fórmula | Leitura |
|---|---|---|
| Teto energético diurno | `L × H_d` | se ≪ E, ampliar entrada |
| Teto de sessões diurnas | `V × H_d ÷ t̄` | se < devoluções/dia, faltam vagas ou DC |
| Sessões noturnas | `V` por noite | carro a 80% segura a vaga até abrir |
| Maior janela fechada | ex.: sáb 12h → seg 8h | só os `V` plugados no fechamento carregam |
| Pressão na reabertura | devoluções acumuladas ÷ `V` | fila da manhã após fechamento longo |

## Divisão (`divisao`)

- `igual`: todos na mesma velocidade (enchimento de água).
- `prioridade`: o primeiro da fila leva tudo o que pode; os últimos podem ficar com 0.
- Só importa quando o limite da agência ou um carregador de 2 saídas está saturado. Com só AC abaixo do limite, é indiferente.

## Exemplo trabalhado: Bangkok (6 vagas, b3_45 = 40,5 kW, seg–sex 8–18h, sáb 8–12h)

Capacidade: teto energético diurno 405 kWh contra ~127 kWh/dia necessários; fechamento longo de 44 h (sáb 12h → seg 8h).

Ponta: fecha às 18h e tem 11 h entre 21h e 8h; pior caso em AC-7 ~6,5 h. **`evitar_ponta = true` é dominante**, e o motor confirma: com e sem, os clientes são idênticos.

Resultados do motor (janela pública, `evitar_ponta = true`, b3_45):

| Carregadores | menor_soc | chegada | proxima_retirada |
|---|---|---|---|
| 1× ac_7 | 161 perdidos | 147 | 134 |
| 2× ac_7 | 73 | **46** | 55 |
| 2× ac_11 ou 1× ac_22x2 | 45 | 32 | **24** |
| 3× ac_7 | 2 | 1 | 1 |
| **1× dc_30** | **0** | **0** | **0** |
| 1× ac_7 + 1× dc_30 | 0 | 0 | 0 |
| 1× dc_60x2 | 0 | 0 | 0 |

Leituras:

- Bangkok é folgada: **uma única saída DC-30 já atende todos**. A decisão real vai ser de **custo** (DC-30 vs. 3× AC-7), que só se resolve em H4.
- Quando a infraestrutura é escassa, a prioridade faz muita diferença (46 vs. 73 perdidos com 2× AC-7), e a melhor muda conforme o carregador. Não há prioridade universalmente melhor: simular as três.
- Esses números são do **nosso motor**. Valem como decisão só depois de a bateria de validação bater com o juiz.
