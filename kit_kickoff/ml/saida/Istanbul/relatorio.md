# Análise de ML — Istanbul

Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). Nenhuma chamada à API.

## Ficha

| item | valor |
|---|---|
| agencia | Istanbul |
| vagas | 4 |
| frota | 235 |
| entrada_existente | b3_45 |
| limite_kw | 40.5 |
| horas_abertas_semana | 168.0 |
| aberta_24h | True |
| aberta_na_ponta | True |
| fecha_ate_18h | False |
| contratos | 1293 |
| contratos_semana | 323.25 |
| kwh_dia | 843.0744501706497 |
| kwh_dia_por_vaga | 210.76861254266242 |
| pressao_energia | 0.8673605454430553 |
| devolucoes_dia | 39.357142857142854 |
| devolucoes_dia_por_vaga | 9.839285714285714 |
| pct_devolve_na_abertura | 0.016241299303944315 |
| folga_por_rank | {1: 2, 2: 4, 3: 2, 4: 0} |
| em_contrato_t0_pct | 0.8170212765957446 |

## Curvas de recarga (não supervisionado)

KMeans com k=2 (silhueta 0.34); PCA explica [0.694, 0.149] da variância.

| modelo | categoria | frota_n | ac_kw | dc_pico_kw | dc_medio_20_80 | dc_queda | classe_recarga_nome | carregador_suficiente |
|---|---|---|---|---|---|---|---|---|
| JAC E-JS1 | Bronze | 31 | 6.6 | 19.2 | 18.56 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| Renault Kwid E-Tech | Bronze | 30 | 7.4 | 26.9 | 26.04 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| BYD Dolphin Mini GS | Prata | 38 | 6.6 | 38.1 | 36.87 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| Geely EX2 Pro | Prata | 51 | 6.6 | 72.6 | 62.73 | 0.57 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| BYD Dolphin GS | Ouro | 38 | 7.0 | 58.35 | 46.67 | 0.47 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| MG4 Urban Comfort | Ouro | 36 | 11.0 | 80.0 | 76.94 | 0.81 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| BYD Dolphin Plus | Diamante | 4 | 11.0 | 79.6 | 68.8 | 0.57 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| Leapmotor B10 BEV | Diamante | 7 | 11.0 | 140.0 | 105.47 | 0.38 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |

Energia de recarga por classe (quanto da demanda cada tipo de curva gera):

| classe_recarga_nome | carregador_suficiente | sessoes | kwh | pct_kwh |
|---|---|---|---|---|
| AC~7kW DC~38kW bat~36kWh | dc_60x2 | 751 | 16415.6 | 55.1 |
| AC~7kW DC~38kW bat~36kWh | dc_30 | 412 | 6696.4 | 22.5 |
| AC~11kW DC~84kW bat~53kWh | dc_120x2 | 284 | 6694.6 | 22.5 |

## Energia

### Por contrato (n=1212, validação deixando 1 semana de fora)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (frota da categoria) | 0.805 | 0.97 | -0.584 |
| Ridge | 0.853 | 0.97 | -0.014 |
| GBM (física + dados) | 1.024 | 0.962 | 0.145 |
| GBM (só dados brutos) | 1.027 | 0.961 | 0.059 |

Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:

| feature | delta_MAE_kWh |
|---|---|
| km_devolucao | 7.708 |
| rank | 4.749 |
| hora_ret | 0.016 |
| autonomia_min_km | 0.008 |
| devolve_na_abertura | 0.0 |
| hora_dev | -0.001 |
| dia_sem_ret | -0.002 |
| dia_sem_dev | -0.003 |
| dur_h | -0.004 |

Informação mútua com o kWh real:

| feature | info_mutua |
|---|---|
| kwh_esperado | 3.595 |
| soc_esperado | 3.196 |
| km_devolucao | 2.949 |
| rank | 0.489 |
| autonomia_min_km | 0.291 |
| hora_dev | 0.019 |
| dur_h | 0.019 |
| hora_ret | 0.005 |
| dia_sem_ret | 0.0 |
| dia_sem_dev | 0.0 |

### Por dia (n=28)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (esperado + T0) | 43.633 | 0.809 | 4.234 |
| Ridge | 131.657 | -0.081 | 8.395 |
| GBM | 118.908 | 0.235 | 2.102 |
| GBM só calendário | 146.602 | -0.153 | 0.266 |

### Potência pedida sem limite de entrada

Com {'dc_120x2': 2} e se_2000: pico 219.7 kW; P50 43.1, P90 106.4, P95 128.1, P99 172.4 kW (janelas com carga); carga em 78% do tempo; perdidos sem limite: 0, upgrades: 0.

Horas da semana com mais energia chegando (média das semanas públicas):

| dia_sem | hora | kwh_media | kwh_desvio |
|---|---|---|---|
| 5 | 2 | 85.9 | 51.4 |
| 4 | 18 | 79.6 | 34.0 |
| 5 | 22 | 77.4 | 24.0 |
| 3 | 13 | 69.0 | 23.5 |
| 6 | 1 | 68.3 | 25.1 |
| 1 | 19 | 67.1 | 52.6 |
| 2 | 8 | 66.6 | 10.2 |
| 3 | 21 | 63.0 | 46.5 |
| 4 | 9 | 60.3 | 19.2 |
| 5 | 19 | 60.2 | 27.2 |

## Segmentos e tipos de dia (não supervisionado)

### Segmentos de contrato (k=2, silhueta 0.68)

| segmento | contratos | dur_h_mediana | hora_ret_media | km_dev_medio | rank_medio | pct_devolve_abertura | kwh_esperado_medio | kwh_real_medio |
|---|---|---|---|---|---|---|---|---|
| 0 | 17 | 57.72 | 16.3 | 76.59 | 2.0 | 1.0 | 18.84 | 20.02 |
| 1 | 1195 | 68.42 | 17.29 | 64.4 | 2.09 | 0.0 | 21.18 | 21.29 |

### Tipos de dia (k=2, silhueta 0.06)

| tipo_dia | dias | retiradas_media | devolucoes_media | kwh_esperado_medio | dias_da_semana |
|---|---|---|---|---|---|
| 0 | 10 | 42.4 | 23.4 | 481.6 | Seg×2, Ter×2, Qua×1, Qui×2, Sex×1, Dom×2 |
| 1 | 18 | 47.6 | 46.4 | 1009.7 | Seg×2, Ter×2, Qua×3, Qui×2, Sex×3, Sáb×4, Dom×2 |

### Anomalias: 37 contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`

## Carregadores (surrogate supervisionado)

151 simulações em 44 s; 70 combinações × 12 políticas previstas.

Qualidade (validação cruzada 5 dobras):

| métrica | R2_cv | MAE_cv | média |
|---|---|---|---|
| nao_atendidos | 0.993 | 14.26 | 401.848 |
| upgrades | 0.98 | 7.118 | 109.132 |
| energia_ponta_kwh | 0.999 | 14.824 | 817.323 |
| pico_kw | 0.999 | 0.108 | 32.134 |

O que mais pesa nos clientes perdidos (importância por permutação):

| feature | delta_MAE |
|---|---|
| kw_nominal | 240.492 |
| saidas_dc | 89.493 |
| saidas_ac | 30.352 |
| evitar_ponta | 26.901 |
| prio_menor_soc | 10.491 |
| n_carregadores | 5.865 |
| kw_ac | 4.509 |
| prio_chegada | 3.286 |
| qtd_ac_11 | 2.885 |
| prio_proxima | 1.491 |

### Melhores candidatos (confirmados no motor)

Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | nao_atendidos | upgrades | energia_ponta_kwh | pico_kw |
|---|---|---|---|---|---|---|---|---|
| 1×ac_11 + 2×dc_30 | chegada | igual | False | 71.0 | 45 | 26 | 2384.5 | 40.5 |
| 1×ac_7 + 2×dc_30 | chegada | igual | False | 67.0 | 45 | 28 | 2380.2 | 40.5 |
| 2×ac_7 + 2×dc_30 | chegada | igual | False | 74.0 | 45 | 29 | 2385.7 | 40.5 |
| 2×ac_7 + 1×dc_60x2 | chegada | igual | False | 74.0 | 46 | 30 | 2381.9 | 40.5 |
| 3×ac_7 + 1×dc_30 | chegada | igual | False | 51.0 | 47 | 27 | 2380.9 | 40.5 |
| 1×ac_22x2 + 1×dc_60x2 | chegada | igual | False | 82.0 | 47 | 29 | 2381.9 | 40.5 |
| 1×ac_22x2 + 2×dc_30 | chegada | igual | False | 82.0 | 47 | 30 | 2385.4 | 40.5 |
| 2×ac_11 + 2×dc_30 | chegada | igual | False | 82.0 | 47 | 30 | 2385.4 | 40.5 |
| 3×ac_7 + 1×dc_30 | chegada | prioridade | False | 51.0 | 54 | 23 | 2368.6 | 40.5 |
| 3×ac_7 + 1×dc_30 | proxima_retirada | igual | False | 51.0 | 57 | 81 | 2379.9 | 40.5 |

Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).

### Fronteira de Pareto (perdidos previstos × kW nominal)

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | p_nao_atendidos | p_upgrades |
|---|---|---|---|---|---|---|
| 1×ac_7 | proxima_retirada | prioridade | False | 7.0 | 999.5 | 103.9 |
| 1×ac_11 | proxima_retirada | igual | False | 11.0 | 964.5 | 126.7 |
| 2×ac_7 | proxima_retirada | prioridade | False | 14.0 | 823.8 | 156.1 |
| 1×ac_11 + 1×ac_7 | proxima_retirada | prioridade | False | 18.0 | 772.4 | 176.2 |
| 3×ac_7 | proxima_retirada | prioridade | False | 21.0 | 642.1 | 211.8 |
| 1×ac_11 + 2×ac_7 | proxima_retirada | igual | False | 25.0 | 586.8 | 258.2 |
| 4×ac_7 | chegada | igual | False | 28.0 | 420.0 | 156.8 |
| 1×dc_30 | proxima_retirada | igual | False | 30.0 | 407.4 | 269.7 |
| 2×ac_11 + 2×ac_7 | proxima_retirada | igual | True | 36.0 | 340.5 | 256.8 |
| 1×ac_7 + 1×dc_30 | chegada | igual | False | 37.0 | 227.2 | 146.8 |
| 1×ac_11 + 1×dc_30 | chegada | igual | False | 41.0 | 176.6 | 87.4 |
| 2×ac_7 + 1×dc_30 | chegada | igual | False | 44.0 | 64.7 | 73.9 |
| 1×ac_11 + 1×ac_7 + 1×dc_30 | chegada | igual | False | 48.0 | 57.0 | 41.2 |
| 3×ac_7 + 1×dc_30 | chegada | igual | False | 51.0 | 31.9 | 29.7 |

_Tempo total: 54 s._