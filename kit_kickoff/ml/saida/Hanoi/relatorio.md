# Análise de ML — Hanoi

Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). Nenhuma chamada à API.

## Ficha

| item | valor |
|---|---|
| agencia | Hanoi |
| vagas | 6 |
| frota | 305 |
| entrada_existente | b3_45 |
| limite_kw | 40.5 |
| horas_abertas_semana | 84.0 |
| aberta_24h | False |
| aberta_na_ponta | True |
| fecha_ate_18h | False |
| contratos | 1167 |
| contratos_semana | 291.75 |
| kwh_dia | 555.7356796296898 |
| kwh_dia_por_vaga | 92.62261327161497 |
| pressao_energia | 1.1434890527359873 |
| devolucoes_dia | 31.75 |
| devolucoes_dia_por_vaga | 5.291666666666667 |
| pct_devolve_na_abertura | 0.4661525278491859 |
| folga_por_rank | {1: 2, 2: 4, 3: 3, 4: 0} |
| em_contrato_t0_pct | 0.9311475409836065 |

## Curvas de recarga (não supervisionado)

KMeans com k=2 (silhueta 0.34); PCA explica [0.694, 0.149] da variância.

| modelo | categoria | frota_n | ac_kw | dc_pico_kw | dc_medio_20_80 | dc_queda | classe_recarga_nome | carregador_suficiente |
|---|---|---|---|---|---|---|---|---|
| JAC E-JS1 | Bronze | 40 | 6.6 | 19.2 | 18.56 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| Renault Kwid E-Tech | Bronze | 36 | 7.4 | 26.9 | 26.04 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| BYD Dolphin Mini GS | Prata | 51 | 6.6 | 38.1 | 36.87 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| Geely EX2 Pro | Prata | 68 | 6.6 | 72.6 | 62.73 | 0.57 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| BYD Dolphin GS | Ouro | 52 | 7.0 | 58.35 | 46.67 | 0.47 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| MG4 Urban Comfort | Ouro | 37 | 11.0 | 80.0 | 76.94 | 0.81 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| BYD Dolphin Plus | Diamante | 12 | 11.0 | 79.6 | 68.8 | 0.57 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| Leapmotor B10 BEV | Diamante | 9 | 11.0 | 140.0 | 105.47 | 0.38 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |

Energia de recarga por classe (quanto da demanda cada tipo de curva gera):

| classe_recarga_nome | carregador_suficiente | sessoes | kwh | pct_kwh |
|---|---|---|---|---|
| AC~7kW DC~38kW bat~36kWh | dc_60x2 | 599 | 10643.3 | 53.8 |
| AC~7kW DC~38kW bat~36kWh | dc_30 | 376 | 5331.5 | 26.9 |
| AC~11kW DC~84kW bat~53kWh | dc_120x2 | 188 | 3820.8 | 19.3 |

## Energia

### Por contrato (n=858, validação deixando 1 semana de fora)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (frota da categoria) | 0.972 | 0.95 | -2.067 |
| Ridge | 1.168 | 0.948 | 0.314 |
| GBM (física + dados) | 1.387 | 0.937 | 0.563 |
| GBM (só dados brutos) | 1.55 | 0.92 | -0.58 |

Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:

| feature | delta_MAE_kWh |
|---|---|
| km_devolucao | 8.529 |
| rank | 3.976 |
| hora_ret | 0.012 |
| hora_dev | 0.007 |
| dia_sem_ret | 0.001 |
| devolve_na_abertura | 0.0 |
| autonomia_min_km | -0.006 |
| dia_sem_dev | -0.019 |
| dur_h | -0.024 |

Informação mútua com o kWh real:

| feature | info_mutua |
|---|---|
| kwh_esperado | 3.079 |
| km_devolucao | 2.625 |
| soc_esperado | 2.492 |
| rank | 0.29 |
| autonomia_min_km | 0.103 |
| hora_dev | 0.057 |
| devolve_na_abertura | 0.029 |
| hora_ret | 0.014 |
| dur_h | 0.0 |
| dia_sem_dev | 0.0 |

### Por dia (n=28)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (esperado + T0) | 163.716 | 0.149 | 29.611 |
| Ridge | 99.994 | 0.602 | -6.555 |
| GBM | 144.422 | 0.239 | -2.253 |
| GBM só calendário | 176.939 | -0.153 | 0.93 |

### Potência pedida sem limite de entrada

Com {'dc_120x2': 3} e se_2000: pico 342.3 kW; P50 49.9, P90 208.3, P95 238.5, P99 292.5 kW (janelas com carga); carga em 40% do tempo; perdidos sem limite: 0, upgrades: 0.

Horas da semana com mais energia chegando (média das semanas públicas):

| dia_sem | hora | kwh_media | kwh_desvio |
|---|---|---|---|
| 0 | 7 | 283.0 | 166.2 |
| 5 | 7 | 199.5 | 59.8 |
| 3 | 7 | 166.1 | 53.8 |
| 4 | 7 | 158.9 | 54.0 |
| 6 | 8 | 138.0 | 56.5 |
| 2 | 7 | 136.8 | 70.7 |
| 1 | 7 | 136.5 | 63.3 |
| 5 | 18 | 46.0 | 23.8 |
| 1 | 14 | 44.4 | 24.8 |
| 5 | 17 | 41.5 | 27.7 |

## Segmentos e tipos de dia (não supervisionado)

### Segmentos de contrato (k=2, silhueta 0.27)

| segmento | contratos | dur_h_mediana | hora_ret_media | km_dev_medio | rank_medio | pct_devolve_abertura | kwh_esperado_medio | kwh_real_medio |
|---|---|---|---|---|---|---|---|---|
| 0 | 461 | 73.0 | 13.63 | 83.3 | 1.89 | 0.0 | 17.19 | 17.46 |
| 1 | 397 | 107.82 | 13.95 | 91.07 | 1.94 | 1.0 | 16.66 | 17.13 |

### Tipos de dia (k=2, silhueta 0.21)

| tipo_dia | dias | retiradas_media | devolucoes_media | kwh_esperado_medio | dias_da_semana |
|---|---|---|---|---|---|
| 0 | 4 | 16.5 | 11.2 | 196.2 | Dom×4 |
| 1 | 24 | 45.0 | 34.4 | 601.1 | Seg×4, Ter×4, Qua×4, Qui×4, Sex×4, Sáb×4 |

### Anomalias: 26 contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`

## Carregadores (surrogate supervisionado)

181 simulações em 52 s; 258 combinações × 12 políticas previstas.

Qualidade (validação cruzada 5 dobras):

| métrica | R2_cv | MAE_cv | média |
|---|---|---|---|
| nao_atendidos | 0.977 | 21.029 | 496.68 |
| upgrades | 0.974 | 9.158 | 141.972 |
| energia_ponta_kwh | 0.996 | 32.619 | 957.783 |
| pico_kw | 0.997 | 0.164 | 35.065 |

O que mais pesa nos clientes perdidos (importância por permutação):

| feature | delta_MAE |
|---|---|
| kw_nominal | 146.358 |
| evitar_ponta | 33.278 |
| prio_menor_soc | 19.585 |
| prio_proxima | 10.715 |
| n_carregadores | 4.404 |
| saidas | 4.29 |
| div_prioridade | 3.387 |
| saidas_ac | 2.63 |
| qtd_ac_7 | 1.995 |
| saidas_dc | 1.272 |

### Melhores candidatos (confirmados no motor)

Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | nao_atendidos | upgrades | energia_ponta_kwh | pico_kw |
|---|---|---|---|---|---|---|---|---|
| 1×ac_11 + 1×ac_22x2 + 1×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | False | 123.0 | 209 | 238 | 2427.0 | 40.5 |
| 1×ac_11 + 3×ac_7 + 1×dc_120x2 | proxima_retirada | prioridade | False | 152.0 | 215 | 254 | 2419.5 | 40.5 |
| 1×ac_11 + 1×ac_22x2 + 1×dc_120x2 + 1×dc_30 | proxima_retirada | prioridade | False | 183.0 | 217 | 242 | 2425.5 | 40.5 |
| 4×ac_7 + 1×dc_120x2 | proxima_retirada | prioridade | False | 148.0 | 219 | 252 | 2392.9 | 40.5 |
| 1×ac_11 + 1×ac_22x2 + 3×dc_30 | proxima_retirada | prioridade | False | 123.0 | 222 | 241 | 2425.1 | 40.5 |
| 1×ac_22x2 + 2×ac_7 + 1×dc_120x2 | proxima_retirada | prioridade | False | 156.0 | 223 | 252 | 2408.1 | 40.5 |
| 2×ac_11 + 1×ac_22x2 + 1×dc_120x2 | proxima_retirada | prioridade | False | 164.0 | 232 | 246 | 2391.6 | 40.5 |
| 1×ac_11 + 1×ac_22x2 + 1×ac_7 + 1×dc_60x2 | proxima_retirada | prioridade | False | 100.0 | 233 | 249 | 2399.9 | 40.5 |
| 1×ac_11 + 1×ac_22x2 + 1×ac_7 + 1×dc_120x2 | proxima_retirada | prioridade | False | 160.0 | 233 | 249 | 2399.9 | 40.5 |
| 1×ac_11 + 1×ac_22x2 + 1×dc_120x2 + 1×dc_30 | chegada | prioridade | False | 183.0 | 238 | 121 | 2420.3 | 40.5 |

Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).

### Fronteira de Pareto (perdidos previstos × kW nominal)

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | p_nao_atendidos | p_upgrades |
|---|---|---|---|---|---|---|
| 1×ac_7 | proxima_retirada | igual | False | 7.0 | 914.6 | 119.5 |
| 1×ac_11 | proxima_retirada | igual | False | 11.0 | 897.6 | 121.7 |
| 2×ac_7 | proxima_retirada | igual | False | 14.0 | 786.3 | 189.8 |
| 1×ac_11 + 1×ac_7 | proxima_retirada | igual | False | 18.0 | 782.9 | 190.9 |
| 3×ac_7 | proxima_retirada | igual | False | 21.0 | 771.8 | 207.5 |
| 1×ac_22x2 | proxima_retirada | igual | False | 22.0 | 753.2 | 198.1 |
| 1×ac_11 + 2×ac_7 | proxima_retirada | igual | True | 25.0 | 628.6 | 220.4 |
| 4×ac_7 | proxima_retirada | igual | False | 28.0 | 555.5 | 253.2 |
| 1×dc_30 | proxima_retirada | prioridade | False | 30.0 | 551.0 | 252.6 |
| 1×ac_11 + 3×ac_7 | proxima_retirada | prioridade | False | 32.0 | 511.7 | 264.8 |
| 5×ac_7 | proxima_retirada | prioridade | False | 35.0 | 403.4 | 280.6 |
| 1×ac_11 + 4×ac_7 | proxima_retirada | prioridade | False | 39.0 | 392.5 | 279.1 |
| 1×ac_11 + 5×ac_7 | proxima_retirada | prioridade | False | 46.0 | 377.0 | 280.9 |
| 1×ac_11 + 1×ac_7 + 1×dc_30 | proxima_retirada | prioridade | False | 48.0 | 364.1 | 276.4 |
| 2×ac_11 + 4×ac_7 | proxima_retirada | prioridade | False | 50.0 | 338.6 | 281.1 |

_Tempo total: 59 s._