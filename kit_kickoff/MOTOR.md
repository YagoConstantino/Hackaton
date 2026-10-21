# Motor da equipe — estado e decisões

`kickoff/motor.py` com as etapas 2 a 7 implementadas. Nada de Bangkok está fixo no código: tudo vem do `Cenario` carregado de `dados/<Agencia>/`.

## Como rodar

```
python -m unittest discover -s testes          # 28 testes, incluindo os números do regulamento
python simular.py exemplo_submissao.json
python validacao/validar_juiz.py               # bateria contra o juiz (só Bangkok, grátis; exige GAMEDAY_URL/TOKEN)
python validacao/validar_juiz.py --local       # só compara com respostas já salvas
```

## Testes cobertos (números do regulamento)

| Seção | Verifica |
|---|---|
| 4.1 | SOC de devolução por km e teto no SOC de saída |
| 5.1 / 6.3.1 | escolha do carro (Geely → Dolphin Mini → MG4), desempate por id, fechada não retira |
| 6.3.2 | Dolphin GS 20→80% num DC-60 em 36,7 min |
| 6.3.3 | menor_soc ABDC, chegada ABCD, proxima_retirada CDBA |
| 6.3.4 | escolha do carregador (DC-60 dividido vence AC-22) |
| 6.3.5 | 10,125 / 26,6–13,9 / 21,18 / 26,6–53,4 kW |
| 6.3.6 | MG4 termina 19h sem evitar (11 kWh na ponta) e 22h com evitar (0 kWh) |
| 5.2 / 5.3 | invariantes numa rodada completa em 4 regimes: não pluga/despluga fechada, nunca passa do limite, nunca carrega acima de 80%, retirada sempre ≥ 80% e sem downgrade |
| 11 | eventos de limite e de carregador fora |

## Pontos de interpretação (ajustar se o juiz divergir)

| Constante / função | Leitura adotada | Alternativa |
|---|---|---|
| `ESTIMATIVA_PONTO = "simples"` | estimativa do carregador (6.3.4) = `min(nominal ÷ n, curva do carro)` | `"agua"`: enchimento de água com quem já está |
| `_proxima_reserva` | "contrato ainda não retirado" = contrato cuja hora de retirada ainda não foi processada (perdidos também saem da lista) | manter perdidos como reserva |
| Camada 1 com `divisao = prioridade` | nominal do carregador repartida em sequência pela prioridade (exemplo 6.3.5: Geely 60, Dolphin 0) | — |
| `on_fim_recarga` | ajusta o SOC exatamente ao fim do degrau (remove resíduo de ponto flutuante) | — |
| `interpretar_evento` | HIPÓTESE `[tipo, agencia, inicio, fim, valor]`, tipos `limite` e `carregador` | trocar só esta função quando o formato for anunciado |
| `REGISTRO_FILA` | série `fila_max` como o juiz reporta: devolução grava o valor real; carro desplugado a 80% grava 0; retirada e troca de degrau não gravam. **Confirmado** no teste 01 (2.688 janelas, soma 803 = juiz). Abertura e fechamento ainda indefinidos | trocar `"real"`/`"zero"`/`"skip"` por evento |
| `EVENTO_QUEBRA_DESPLUGA = False` | carro em carregador quebrado fica plugado a 0 kW | `True`: volta para a fila |

Se o `comparar.py` mostrar divergência, a primeira janela "DIVERGE em" indica o instante; os suspeitos são, nessa ordem, as linhas acima.

## Fila real × fila reportada

O juiz reporta a série `fila_max` com um critério próprio (tabela acima), que **não é** o tamanho real da fila em cada janela. Só afeta essa série (não afeta a nota nem a simulação). O motor guarda as duas:

- `Motor.trace`: critério do juiz (é o que `comparar.py` confere);
- `Motor.trace_real`: tamanho verdadeiro da fila, para o dashboard (use `medicao.series(..., trace_real, ...)`).

## Bateria de validação (`validacao/`)

| Arquivo | Regime exercitado |
|---|---|
| 01_exemplo | o exemplo do kit |
| 02_so_ac_chegada | só AC, limite levemente saturado, FIFO |
| 03_dc_prioridade | DC de 2 saídas saturando 40,5 kW, `proxima_retirada` + divisão `prioridade` |
| 04_dc_igual | 3× DC de 2 saídas, enchimento de água nas duas camadas |
| 05_ponta_b3_75 | `evitar_ponta`, ampliação para b3_75, AC-22 |
| 06_a4_demanda50 | A4 com demanda 50 kW, DC-120, divisão `prioridade` |
| 07_proxret_ponta | `proxima_retirada` + `evitar_ponta` + divisão `igual` |
| 08_minimo_perdas | 1 só AC-7: muitos perdidos e upgrades (testa a escolha na retirada) |

Meta: `OK: bate com o juiz` nas 8.
