# Análise de ML — Marrakech

Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). Nenhuma chamada à API.

## Ficha

| item | valor |
|---|---|
| agencia | Marrakech |
| vagas | 10 |
| frota | 480 |
| entrada_existente | b3_45 |
| limite_kw | 40.5 |
| horas_abertas_semana | 61.0 |
| aberta_24h | False |
| aberta_na_ponta | False |
| fecha_ate_18h | True |
| contratos | 1230 |
| contratos_semana | 307.5 |
| kwh_dia | 505.6264945070703 |
| kwh_dia_por_vaga | 50.56264945070703 |
| pressao_energia | 1.4326595675164913 |
| devolucoes_dia | 29.142857142857142 |
| devolucoes_dia_por_vaga | 2.914285714285714 |
| pct_devolve_na_abertura | 0.6195121951219512 |
| folga_por_rank | {1: 7, 2: 7, 3: 12, 4: 0} |
| em_contrato_t0_pct | 0.9166666666666666 |

## Curvas de recarga (não supervisionado)

KMeans com k=2 (silhueta 0.34); PCA explica [0.694, 0.149] da variância.

| modelo | categoria | frota_n | ac_kw | dc_pico_kw | dc_medio_20_80 | dc_queda | classe_recarga_nome | carregador_suficiente |
|---|---|---|---|---|---|---|---|---|
| JAC E-JS1 | Bronze | 65 | 6.6 | 19.2 | 18.56 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| Renault Kwid E-Tech | Bronze | 79 | 7.4 | 26.9 | 26.04 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| BYD Dolphin Mini GS | Prata | 67 | 6.6 | 38.1 | 36.87 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| Geely EX2 Pro | Prata | 75 | 6.6 | 72.6 | 62.73 | 0.57 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| BYD Dolphin GS | Ouro | 97 | 7.0 | 58.35 | 46.67 | 0.47 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| MG4 Urban Comfort | Ouro | 70 | 11.0 | 80.0 | 76.94 | 0.81 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| BYD Dolphin Plus | Diamante | 17 | 11.0 | 79.6 | 68.8 | 0.57 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| Leapmotor B10 BEV | Diamante | 10 | 11.0 | 140.0 | 105.47 | 0.38 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |

Energia de recarga por classe (quanto da demanda cada tipo de curva gera):

| classe_recarga_nome | carregador_suficiente | sessoes | kwh | pct_kwh |
|---|---|---|---|---|
| AC~7kW DC~38kW bat~36kWh | dc_60x2 | 479 | 8454.5 | 47.0 |
| AC~7kW DC~38kW bat~36kWh | dc_30 | 427 | 5654.3 | 31.5 |
| AC~11kW DC~84kW bat~53kWh | dc_120x2 | 194 | 3861.9 | 21.5 |

## Energia

### Por contrato (n=620, validação deixando 1 semana de fora)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (frota da categoria) | 1.398 | 0.911 | -4.986 |
| Ridge | 1.68 | 0.914 | 0.364 |
| GBM (física + dados) | 1.985 | 0.895 | -0.004 |
| GBM (só dados brutos) | 2.054 | 0.894 | -0.364 |

Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:

| feature | delta_MAE_kWh |
|---|---|
| km_devolucao | 8.27 |
| rank | 3.778 |
| hora_dev | 0.024 |
| hora_ret | 0.018 |
| dia_sem_ret | 0.014 |
| autonomia_min_km | 0.013 |
| devolve_na_abertura | -0.0 |
| dur_h | -0.016 |
| dia_sem_dev | -0.036 |

Informação mútua com o kWh real:

| feature | info_mutua |
|---|---|
| kwh_esperado | 2.77 |
| km_devolucao | 2.467 |
| soc_esperado | 2.192 |
| rank | 0.18 |
| autonomia_min_km | 0.083 |
| hora_dev | 0.021 |
| dia_sem_dev | 0.012 |
| dur_h | 0.0 |
| hora_ret | 0.0 |
| dia_sem_ret | 0.0 |

### Por dia (n=28)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (esperado + T0) | 264.864 | 0.23 | 52.091 |
| Ridge | 75.766 | 0.939 | -4.952 |
| GBM | 240.914 | 0.28 | -5.483 |
| GBM só calendário | 281.867 | -0.039 | 2.108 |

### Potência pedida sem limite de entrada

Com {'dc_120x2': 5} e se_2000: pico 512.4 kW; P50 49.7, P90 353.9, P95 407.5, P99 455.7 kW (janelas com carga); carga em 30% do tempo; perdidos sem limite: 0, upgrades: 0.

Horas da semana com mais energia chegando (média das semanas públicas):

| dia_sem | hora | kwh_media | kwh_desvio |
|---|---|---|---|
| 0 | 7 | 358.8 | 234.5 |
| 3 | 7 | 164.0 | 64.9 |
| 2 | 7 | 156.1 | 88.7 |
| 5 | 7 | 153.7 | 36.8 |
| 1 | 7 | 122.6 | 38.4 |
| 4 | 7 | 71.6 | 35.6 |
| 1 | 11 | 43.4 | 25.1 |
| 4 | 10 | 33.7 | 23.9 |
| 1 | 9 | 32.7 | 24.8 |
| 5 | 9 | 24.3 | 27.3 |

## Segmentos e tipos de dia (não supervisionado)

### Segmentos de contrato (k=2, silhueta 0.30)

| segmento | contratos | dur_h_mediana | hora_ret_media | km_dev_medio | rank_medio | pct_devolve_abertura | kwh_esperado_medio | kwh_real_medio |
|---|---|---|---|---|---|---|---|---|
| 0 | 234 | 103.27 | 11.14 | 86.53 | 1.71 | 0.0 | 15.14 | 15.77 |
| 1 | 386 | 186.04 | 11.82 | 81.78 | 1.76 | 1.0 | 16.1 | 17.04 |

### Tipos de dia (k=4, silhueta 0.25)

| tipo_dia | dias | retiradas_media | devolucoes_media | kwh_esperado_medio | dias_da_semana |
|---|---|---|---|---|---|
| 0 | 4 | 0.0 | 0.0 | 0.0 | Dom×4 |
| 1 | 4 | 33.2 | 25.2 | 435.1 | Sáb×4 |
| 2 | 17 | 48.6 | 29.2 | 492.9 | Seg×1, Ter×4, Qua×4, Qui×4, Sex×4 |
| 3 | 3 | 90.0 | 73.0 | 1345.7 | Seg×3 |

### Anomalias: 19 contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`

## Carregadores (surrogate supervisionado)

188 simulações em 69 s; 1805 combinações × 12 políticas previstas.

Qualidade (validação cruzada 5 dobras):

| métrica | R2_cv | MAE_cv | média |
|---|---|---|---|
| nao_atendidos | 0.983 | 15.786 | 620.479 |
| upgrades | 0.976 | 7.475 | 154.649 |
| energia_ponta_kwh | 0.962 | 84.457 | 631.682 |
| pico_kw | 0.995 | 0.176 | 36.393 |

O que mais pesa nos clientes perdidos (importância por permutação):

| feature | delta_MAE |
|---|---|
| prio_menor_soc | 89.188 |
| kw_nominal | 78.034 |
| saidas | 21.194 |
| prio_chegada | 12.823 |
| div_prioridade | 11.408 |
| prio_proxima | 9.272 |
| n_carregadores | 3.842 |
| saidas_dc | 1.708 |
| qtd_ac_11 | 0.68 |
| qtd_ac_7 | 0.437 |

### Melhores candidatos (confirmados no motor)

Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | nao_atendidos | upgrades | energia_ponta_kwh | pico_kw |
|---|---|---|---|---|---|---|---|---|
| 2×ac_11 + 2×dc_120x2 + 2×dc_60x2 | proxima_retirada | prioridade | False | 382.0 | 295 | 238 | 2418.7 | 40.5 |
| 2×ac_11 + 3×dc_120x2 + 1×dc_60x2 | proxima_retirada | prioridade | False | 442.0 | 295 | 238 | 2418.7 | 40.5 |
| 2×ac_11 + 4×dc_120x2 | proxima_retirada | prioridade | False | 502.0 | 295 | 238 | 2418.7 | 40.5 |
| 4×dc_120x2 + 2×dc_30 | proxima_retirada | prioridade | False | 540.0 | 297 | 234 | 2430.0 | 40.5 |
| 2×ac_11 + 2×dc_120x2 + 2×dc_60x2 | proxima_retirada | prioridade | True | 382.0 | 297 | 247 | 0.0 | 40.5 |
| 1×ac_22x2 + 3×dc_120x2 + 2×dc_30 | proxima_retirada | prioridade | False | 442.0 | 304 | 240 | 2419.9 | 40.5 |
| 3×dc_120x2 + 2×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | False | 480.0 | 305 | 241 | 2429.9 | 40.5 |
| 2×dc_120x2 + 2×dc_30 + 2×dc_60x2 | proxima_retirada | prioridade | False | 420.0 | 308 | 248 | 2430.0 | 40.5 |
| 1×ac_22x2 + 2×dc_120x2 + 2×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | False | 382.0 | 309 | 236 | 2419.9 | 40.5 |
| 1×ac_22x2 + 2×dc_120x2 + 2×dc_30 + 1×dc_60x2 | proxima_retirada | prioridade | True | 382.0 | 310 | 236 | 0.0 | 40.5 |

Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).

### Fronteira de Pareto (perdidos previstos × kW nominal)

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | p_nao_atendidos | p_upgrades |
|---|---|---|---|---|---|---|
| 1×ac_7 | proxima_retirada | prioridade | False | 7.0 | 966.9 | 109.1 |
| 1×ac_11 | proxima_retirada | prioridade | False | 11.0 | 954.5 | 118.8 |
| 2×ac_7 | proxima_retirada | prioridade | False | 14.0 | 851.5 | 164.0 |
| 1×ac_11 + 1×ac_7 | proxima_retirada | prioridade | True | 18.0 | 848.3 | 174.1 |
| 3×ac_7 | proxima_retirada | prioridade | False | 21.0 | 821.6 | 170.7 |
| 1×ac_22x2 | proxima_retirada | prioridade | False | 22.0 | 819.8 | 172.1 |
| 4×ac_7 | proxima_retirada | prioridade | False | 28.0 | 733.9 | 217.9 |
| 1×dc_30 | proxima_retirada | prioridade | False | 30.0 | 655.6 | 211.9 |
| 5×ac_7 | proxima_retirada | prioridade | True | 35.0 | 616.2 | 233.1 |
| 1×ac_7 + 1×dc_30 | proxima_retirada | igual | True | 37.0 | 608.9 | 230.3 |
| 1×ac_11 + 1×dc_30 | proxima_retirada | prioridade | False | 41.0 | 563.7 | 224.5 |
| 1×ac_22x2 + 3×ac_7 | proxima_retirada | prioridade | False | 43.0 | 509.7 | 240.4 |
| 2×ac_7 + 1×dc_30 | proxima_retirada | prioridade | False | 44.0 | 493.0 | 229.2 |
| 1×ac_11 + 5×ac_7 | proxima_retirada | prioridade | False | 46.0 | 489.4 | 240.9 |
| 7×ac_7 | proxima_retirada | prioridade | False | 49.0 | 468.7 | 243.2 |

_Tempo total: 78 s._