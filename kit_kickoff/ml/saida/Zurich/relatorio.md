# Análise de ML — Zurich

Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). Nenhuma chamada à API.

## Ficha

| item | valor |
|---|---|
| agencia | Zurich |
| vagas | 4 |
| frota | 255 |
| entrada_existente | b3_75 |
| limite_kw | 67.5 |
| horas_abertas_semana | 66.0 |
| aberta_24h | False |
| aberta_na_ponta | True |
| fecha_ate_18h | False |
| contratos | 867 |
| contratos_semana | 216.75 |
| kwh_dia | 383.46958445598295 |
| kwh_dia_por_vaga | 95.86739611399574 |
| pressao_energia | 0.6025335782697824 |
| devolucoes_dia | 22.5 |
| devolucoes_dia_por_vaga | 5.625 |
| pct_devolve_na_abertura | 0.566320645905421 |
| folga_por_rank | {1: 3, 2: 1, 3: 3, 4: 0} |
| em_contrato_t0_pct | 0.8862745098039215 |

## Curvas de recarga (não supervisionado)

KMeans com k=2 (silhueta 0.34); PCA explica [0.694, 0.149] da variância.

| modelo | categoria | frota_n | ac_kw | dc_pico_kw | dc_medio_20_80 | dc_queda | classe_recarga_nome | carregador_suficiente |
|---|---|---|---|---|---|---|---|---|
| JAC E-JS1 | Bronze | 42 | 6.6 | 19.2 | 18.56 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| Renault Kwid E-Tech | Bronze | 49 | 7.4 | 26.9 | 26.04 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| BYD Dolphin Mini GS | Prata | 35 | 6.6 | 38.1 | 36.87 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| Geely EX2 Pro | Prata | 23 | 6.6 | 72.6 | 62.73 | 0.57 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| BYD Dolphin GS | Ouro | 49 | 7.0 | 58.35 | 46.67 | 0.47 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| MG4 Urban Comfort | Ouro | 39 | 11.0 | 80.0 | 76.94 | 0.81 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| BYD Dolphin Plus | Diamante | 11 | 11.0 | 79.6 | 68.8 | 0.57 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| Leapmotor B10 BEV | Diamante | 7 | 11.0 | 140.0 | 105.47 | 0.38 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |

Energia de recarga por classe (quanto da demanda cada tipo de curva gera):

| classe_recarga_nome | carregador_suficiente | sessoes | kwh | pct_kwh |
|---|---|---|---|---|
| AC~7kW DC~38kW bat~36kWh | dc_60x2 | 443 | 8041.8 | 44.6 |
| AC~11kW DC~84kW bat~53kWh | dc_120x2 | 237 | 5268.6 | 29.2 |
| AC~7kW DC~38kW bat~36kWh | dc_30 | 398 | 4716.3 | 26.2 |

## Energia

### Por contrato (n=823, validação deixando 1 semana de fora)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (frota da categoria) | 0.918 | 0.963 | -1.657 |
| Ridge | 1.059 | 0.963 | -0.018 |
| GBM (física + dados) | 1.188 | 0.955 | 0.373 |
| GBM (só dados brutos) | 1.193 | 0.957 | -0.249 |

Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:

| feature | delta_MAE_kWh |
|---|---|
| km_devolucao | 8.645 |
| rank | 5.646 |
| dur_h | 0.035 |
| hora_ret | 0.033 |
| autonomia_min_km | 0.028 |
| dia_sem_ret | 0.006 |
| hora_dev | 0.005 |
| devolve_na_abertura | 0.0 |
| dia_sem_dev | -0.011 |

Informação mútua com o kWh real:

| feature | info_mutua |
|---|---|
| kwh_esperado | 3.055 |
| km_devolucao | 2.52 |
| soc_esperado | 2.326 |
| rank | 0.268 |
| autonomia_min_km | 0.142 |
| dia_sem_dev | 0.022 |
| hora_dev | 0.015 |
| devolve_na_abertura | 0.012 |
| dur_h | 0.0 |
| dia_sem_ret | 0.0 |

### Por dia (n=28)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (esperado + T0) | 20.814 | 0.991 | 3.321 |
| Ridge | 41.495 | 0.973 | -1.789 |
| GBM | 170.102 | 0.55 | -4.267 |
| GBM só calendário | 257.753 | -0.057 | 2.744 |

### Potência pedida sem limite de entrada

Com {'dc_120x2': 2} e se_2000: pico 220.3 kW; P50 57.2, P90 164.5, P95 181.0, P99 205.6 kW (janelas com carga); carga em 29% do tempo; perdidos sem limite: 0, upgrades: 0.

Horas da semana com mais energia chegando (média das semanas públicas):

| dia_sem | hora | kwh_media | kwh_desvio |
|---|---|---|---|
| 0 | 8 | 568.6 | 348.7 |
| 5 | 8 | 184.2 | 38.9 |
| 1 | 8 | 181.2 | 157.2 |
| 4 | 8 | 179.2 | 64.3 |
| 3 | 8 | 149.0 | 31.0 |
| 2 | 8 | 129.7 | 56.6 |
| 2 | 10 | 43.1 | 25.6 |
| 1 | 13 | 38.6 | 25.7 |
| 2 | 16 | 35.9 | 9.6 |
| 1 | 16 | 35.3 | 36.5 |

## Segmentos e tipos de dia (não supervisionado)

### Segmentos de contrato (k=2, silhueta 0.28)

| segmento | contratos | dur_h_mediana | hora_ret_media | km_dev_medio | rank_medio | pct_devolve_abertura | kwh_esperado_medio | kwh_real_medio |
|---|---|---|---|---|---|---|---|---|
| 0 | 356 | 74.53 | 13.7 | 91.43 | 2.06 | 0.0 | 16.75 | 17.18 |
| 1 | 467 | 136.97 | 13.99 | 88.48 | 2.08 | 1.0 | 17.19 | 17.37 |

### Tipos de dia (k=2, silhueta 0.27)

| tipo_dia | dias | retiradas_media | devolucoes_media | kwh_esperado_medio | dias_da_semana |
|---|---|---|---|---|---|
| 0 | 24 | 23.7 | 19.8 | 330.6 | Ter×4, Qua×4, Qui×4, Sex×4, Sáb×4, Dom×4 |
| 1 | 4 | 74.5 | 38.8 | 700.5 | Seg×4 |

### Anomalias: 25 contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`

## Carregadores (surrogate supervisionado)

151 simulações em 29 s; 70 combinações × 12 políticas previstas.

Qualidade (validação cruzada 5 dobras):

| métrica | R2_cv | MAE_cv | média |
|---|---|---|---|
| nao_atendidos | 0.993 | 12.675 | 291.682 |
| upgrades | 0.959 | 6.439 | 62.132 |
| energia_ponta_kwh | 0.995 | 33.644 | 721.38 |
| pico_kw | 0.999 | 0.238 | 44.204 |

O que mais pesa nos clientes perdidos (importância por permutação):

| feature | delta_MAE |
|---|---|
| kw_nominal | 246.223 |
| evitar_ponta | 11.153 |
| prio_menor_soc | 10.542 |
| prio_proxima | 6.627 |
| saidas_dc | 3.457 |
| qtd_ac_7 | 2.375 |
| saidas | 2.066 |
| kw_ac | 1.22 |
| prio_chegada | 0.919 |
| n_carregadores | 0.833 |

### Melhores candidatos (confirmados no motor)

Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | nao_atendidos | upgrades | energia_ponta_kwh | pico_kw |
|---|---|---|---|---|---|---|---|---|
| 4×dc_30 | proxima_retirada | prioridade | False | 120.0 | 4 | 9 | 2285.8 | 67.5 |
| 1×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | False | 90.0 | 4 | 18 | 2214.3 | 67.5 |
| 2×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | False | 120.0 | 6 | 11 | 2221.3 | 67.5 |
| 2×dc_60x2 | proxima_retirada | prioridade | False | 120.0 | 7 | 12 | 2271.7 | 67.5 |
| 2×ac_7 + 1×dc_60x2 | proxima_retirada | prioridade | False | 74.0 | 7 | 19 | 2219.1 | 67.5 |
| 2×dc_60x2 | proxima_retirada | igual | False | 120.0 | 8 | 11 | 2227.1 | 67.5 |
| 1×ac_22x2 + 1×dc_60x2 | proxima_retirada | prioridade | False | 82.0 | 8 | 20 | 2218.3 | 67.5 |
| 2×ac_11 + 1×dc_60x2 | proxima_retirada | prioridade | False | 82.0 | 8 | 20 | 2218.3 | 67.5 |
| 1×ac_22x2 + 1×dc_60x2 | proxima_retirada | igual | False | 82.0 | 8 | 22 | 2219.3 | 67.5 |
| 1×ac_11 + 1×ac_7 + 1×dc_60x2 | proxima_retirada | prioridade | False | 78.0 | 9 | 21 | 2176.6 | 67.5 |

Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).

### Fronteira de Pareto (perdidos previstos × kW nominal)

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | p_nao_atendidos | p_upgrades |
|---|---|---|---|---|---|---|
| 1×ac_7 | proxima_retirada | prioridade | False | 7.0 | 658.7 | 81.0 |
| 1×ac_11 | proxima_retirada | prioridade | False | 11.0 | 636.7 | 83.0 |
| 2×ac_7 | proxima_retirada | prioridade | False | 14.0 | 558.4 | 102.4 |
| 1×ac_11 + 1×ac_7 | proxima_retirada | prioridade | False | 18.0 | 528.0 | 126.2 |
| 3×ac_7 | proxima_retirada | prioridade | False | 21.0 | 470.1 | 144.9 |
| 1×ac_11 + 2×ac_7 | proxima_retirada | igual | False | 25.0 | 418.8 | 153.7 |
| 4×ac_7 | proxima_retirada | igual | False | 28.0 | 344.5 | 149.7 |
| 2×ac_11 + 2×ac_7 | proxima_retirada | prioridade | False | 36.0 | 289.5 | 170.5 |
| 1×ac_7 + 1×dc_30 | proxima_retirada | prioridade | False | 37.0 | 280.0 | 172.5 |
| 1×ac_11 + 1×dc_30 | proxima_retirada | prioridade | False | 41.0 | 268.2 | 164.6 |
| 2×ac_7 + 1×dc_30 | chegada | prioridade | False | 44.0 | 207.9 | 86.1 |
| 1×ac_11 + 1×ac_7 + 1×dc_30 | proxima_retirada | prioridade | False | 48.0 | 169.0 | 165.2 |
| 3×ac_7 + 1×dc_30 | chegada | prioridade | False | 51.0 | 153.7 | 86.6 |
| 2×ac_11 + 1×dc_30 | chegada | prioridade | False | 52.0 | 146.1 | 63.1 |
| 1×ac_11 + 2×ac_7 + 1×dc_30 | chegada | prioridade | False | 55.0 | 79.3 | 38.5 |

_Tempo total: 36 s._