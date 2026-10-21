# Análise de ML — Bangkok

Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). Nenhuma chamada à API.

## Ficha

| item | valor |
|---|---|
| agencia | Bangkok |
| vagas | 6 |
| frota | 80 |
| entrada_existente | b3_45 |
| limite_kw | 40.5 |
| horas_abertas_semana | 54.0 |
| aberta_24h | False |
| aberta_na_ponta | False |
| fecha_ate_18h | True |
| contratos | 271 |
| contratos_semana | 67.75 |
| kwh_dia | 126.64291839671425 |
| kwh_dia_por_vaga | 21.107153066119043 |
| pressao_energia | 0.4053499902958389 |
| devolucoes_dia | 7.571428571428571 |
| devolucoes_dia_por_vaga | 1.2619047619047619 |
| pct_devolve_na_abertura | 0.6014760147601476 |
| folga_por_rank | {1: 3, 2: 1, 3: 3, 4: 0} |
| em_contrato_t0_pct | 0.725 |

## Curvas de recarga (não supervisionado)

KMeans com k=2 (silhueta 0.34); PCA explica [0.694, 0.149] da variância.

| modelo | categoria | frota_n | ac_kw | dc_pico_kw | dc_medio_20_80 | dc_queda | classe_recarga_nome | carregador_suficiente |
|---|---|---|---|---|---|---|---|---|
| JAC E-JS1 | Bronze | 18 | 6.6 | 19.2 | 18.56 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| Renault Kwid E-Tech | Bronze | 14 | 7.4 | 26.9 | 26.04 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_30 |
| BYD Dolphin Mini GS | Prata | 10 | 6.6 | 38.1 | 36.87 | 0.86 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| Geely EX2 Pro | Prata | 10 | 6.6 | 72.6 | 62.73 | 0.57 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| BYD Dolphin GS | Ouro | 10 | 7.0 | 58.35 | 46.67 | 0.47 | AC~7kW DC~38kW bat~36kWh | dc_60x2 |
| MG4 Urban Comfort | Ouro | 11 | 11.0 | 80.0 | 76.94 | 0.81 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| BYD Dolphin Plus | Diamante | 3 | 11.0 | 79.6 | 68.8 | 0.57 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |
| Leapmotor B10 BEV | Diamante | 4 | 11.0 | 140.0 | 105.47 | 0.38 | AC~11kW DC~84kW bat~53kWh | dc_120x2 |

Energia de recarga por classe (quanto da demanda cada tipo de curva gera):

| classe_recarga_nome | carregador_suficiente | sessoes | kwh | pct_kwh |
|---|---|---|---|---|
| AC~7kW DC~38kW bat~36kWh | dc_60x2 | 136 | 2260.7 | 40.9 |
| AC~11kW DC~84kW bat~53kWh | dc_120x2 | 78 | 1674.8 | 30.3 |
| AC~7kW DC~38kW bat~36kWh | dc_30 | 137 | 1594.6 | 28.8 |

## Energia

### Por contrato (n=271, validação deixando 1 semana de fora)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (frota da categoria) | 0.788 | 0.982 | -0.417 |
| Ridge | 0.847 | 0.981 | 0.007 |
| GBM (física + dados) | 0.982 | 0.976 | 0.254 |
| GBM (só dados brutos) | 1.4 | 0.954 | 0.305 |

Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:

| feature | delta_MAE_kWh |
|---|---|
| km_devolucao | 7.939 |
| rank | 5.014 |
| autonomia_min_km | 0.021 |
| dia_sem_dev | 0.016 |
| hora_ret | 0.004 |
| dur_h | 0.004 |
| dia_sem_ret | 0.001 |
| devolve_na_abertura | -0.001 |
| hora_dev | -0.04 |

Informação mútua com o kWh real:

| feature | info_mutua |
|---|---|
| kwh_esperado | 2.739 |
| km_devolucao | 1.801 |
| soc_esperado | 1.641 |
| rank | 0.352 |
| autonomia_min_km | 0.134 |
| hora_ret | 0.066 |
| dia_sem_dev | 0.033 |
| dur_h | 0.022 |
| dia_sem_ret | 0.02 |
| devolve_na_abertura | 0.006 |

### Por dia (n=28)

| modelo | MAE | R2 | erro_total_pct |
|---|---|---|---|
| física (esperado + T0) | 2.505 | 0.999 | -0.152 |
| Ridge | 14.724 | 0.939 | -3.062 |
| GBM | 62.274 | 0.315 | -5.459 |
| GBM só calendário | 73.825 | 0.015 | 2.785 |

### Potência pedida sem limite de entrada

Com {'dc_120x2': 3} e se_2000: pico 293.6 kW; P50 25.7, P90 149.0, P95 201.3, P99 256.1 kW (janelas com carga); carga em 13% do tempo; perdidos sem limite: 0, upgrades: 0.

Horas da semana com mais energia chegando (média das semanas públicas):

| dia_sem | hora | kwh_media | kwh_desvio |
|---|---|---|---|
| 0 | 8 | 147.3 | 94.3 |
| 3 | 8 | 126.3 | 67.6 |
| 1 | 8 | 85.4 | 53.9 |
| 2 | 8 | 79.7 | 40.5 |
| 4 | 8 | 64.9 | 19.2 |
| 5 | 8 | 55.9 | 23.7 |
| 3 | 9 | 25.7 | 15.7 |
| 1 | 11 | 21.3 | 21.3 |
| 2 | 11 | 20.2 | 20.1 |
| 5 | 10 | 19.3 | 7.0 |

## Segmentos e tipos de dia (não supervisionado)

### Segmentos de contrato (k=2, silhueta 0.28)

| segmento | contratos | dur_h_mediana | hora_ret_media | km_dev_medio | rank_medio | pct_devolve_abertura | kwh_esperado_medio | kwh_real_medio |
|---|---|---|---|---|---|---|---|---|
| 0 | 108 | 69.21 | 12.14 | 96.62 | 2.08 | 0.0 | 16.27 | 16.18 |
| 1 | 163 | 92.87 | 12.74 | 89.25 | 2.07 | 1.0 | 17.08 | 17.26 |

### Tipos de dia (k=4, silhueta 0.16)

| tipo_dia | dias | retiradas_media | devolucoes_media | kwh_esperado_medio | dias_da_semana |
|---|---|---|---|---|---|
| 0 | 10 | 3.5 | 3.9 | 54.3 | Qui×1, Sex×1, Sáb×4, Dom×4 |
| 1 | 6 | 8.7 | 9.2 | 183.2 | Ter×2, Qua×2, Qui×1, Sex×1 |
| 2 | 11 | 15.2 | 9.0 | 144.7 | Seg×3, Ter×2, Qua×2, Qui×2, Sex×2 |
| 3 | 1 | 17.0 | 19.0 | 312.2 | Seg×1 |

### Anomalias: 9 contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`

## Carregadores (surrogate supervisionado)

181 simulações em 23 s; 258 combinações × 12 políticas previstas.

Qualidade (validação cruzada 5 dobras):

| métrica | R2_cv | MAE_cv | média |
|---|---|---|---|
| nao_atendidos | 0.984 | 1.134 | 16.061 |
| upgrades | 0.934 | 0.746 | 5.906 |
| energia_ponta_kwh | 0.978 | 8.451 | 70.227 |
| pico_kw | 0.997 | 0.15 | 35.059 |

O que mais pesa nos clientes perdidos (importância por permutação):

| feature | delta_MAE |
|---|---|
| kw_nominal | 14.244 |
| prio_proxima | 0.703 |
| prio_menor_soc | 0.452 |
| kw_ac | 0.307 |
| saidas_dc | 0.142 |
| saidas | 0.045 |
| saidas_ac | 0.016 |
| evitar_ponta | 0.014 |
| qtd_ac_22x2 | 0.004 |
| qtd_dc_60x2 | 0.002 |

### Melhores candidatos (confirmados no motor)

Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | nao_atendidos | upgrades | energia_ponta_kwh | pico_kw |
|---|---|---|---|---|---|---|---|---|
| 1×dc_30 | menor_soc | prioridade | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | proxima_retirada | prioridade | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | chegada | prioridade | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | menor_soc | igual | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | proxima_retirada | igual | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | chegada | igual | True | 30.0 | 0 | 0 | 0.0 | 30.0 |
| 1×dc_30 | proxima_retirada | prioridade | False | 30.0 | 0 | 0 | 53.2 | 30.0 |
| 1×dc_30 | proxima_retirada | igual | False | 30.0 | 0 | 0 | 53.2 | 30.0 |
| 4×ac_7 | proxima_retirada | prioridade | False | 28.0 | 1 | 0 | 301.2 | 28.0 |
| 1×ac_22x2 + 1×ac_7 | chegada | igual | False | 29.0 | 1 | 0 | 347.1 | 29.0 |

Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).

### Fronteira de Pareto (perdidos previstos × kW nominal)

| config | pol_prioridade | pol_divisao | pol_evitar_ponta | kw_nominal | p_nao_atendidos | p_upgrades |
|---|---|---|---|---|---|---|
| 1×ac_7 | proxima_retirada | prioridade | False | 7.0 | 133.8 | 48.9 |
| 1×ac_11 | proxima_retirada | igual | True | 11.0 | 114.9 | 53.0 |
| 2×ac_7 | proxima_retirada | igual | False | 14.0 | 50.4 | 59.1 |
| 1×ac_11 + 1×ac_7 | proxima_retirada | igual | False | 18.0 | 33.9 | 54.6 |
| 3×ac_7 | proxima_retirada | prioridade | False | 21.0 | 26.1 | 48.6 |
| 2×ac_11 | proxima_retirada | prioridade | False | 22.0 | 22.1 | 48.3 |
| 1×ac_11 + 2×ac_7 | proxima_retirada | prioridade | True | 25.0 | 1.0 | 1.0 |
| 4×ac_7 | proxima_retirada | igual | False | 28.0 | 0.1 | 0.5 |
| 2×ac_11 + 1×ac_7 | proxima_retirada | prioridade | True | 29.0 | 0.0 | 1.1 |

_Tempo total: 29 s._