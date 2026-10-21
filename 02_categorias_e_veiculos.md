# 02 — Categorias e veículos

> **Vale para qualquer agência.** Cada kit traz seus próprios `categorias.csv`, `veiculos.csv` e `curvas/*.md`. O regulamento descreve um catálogo comum (`GET /catalogo`), mas como os arquivos vêm por agência, tratamos todo valor como **possivelmente diferente** e sempre lemos do kit daquela agência. O motor já faz isso (`dados.carregar(dados, agencia)`); nada é fixo no código.

## Estrutura dos arquivos

**`categorias.csv`** — `grupo`, `rank`. Rank maior = categoria superior. As regras só usam o **rank**, nunca o nome: se uma agência tiver mais ou menos categorias, ou nomes diferentes, o motor continua funcionando.

**`veiculos.csv`** — `modelo`, `bateria_kwh`, `autonomia_km`, `recarga_ac_kw`, `recarga_dc_kw` (pico da ficha), `grupo` (categoria). A ficha é informativa: **o juiz usa a curva**, que pode ficar abaixo da ficha.

**`frota_t0.csv`** — quantos carros de cada modelo a agência tem. É aqui que a agência realmente se diferencia: o mix de modelos muda tudo.

## Regras ligadas à categoria (fixas, do regulamento)

- **Upgrade permitido, downgrade nunca**: o contrato aceita qualquer carro com `rank ≥ rank pedido`.
- Upgrade pontua menos que a categoria certa, e muito mais que perder o cliente.
- Escolha na retirada: **menor upgrade → menor SOC → não plugado → menor id**.
- Na fila com `proxima_retirada`, a reserva compatível de um carro é o primeiro contrato pendente com `rank ≤ rank do carro`. Carros de categoria alta "enxergam" mais contratos e tendem a ir na frente.
- A categoria mais alta da agência **não tem para onde fazer upgrade**: é sempre a mais exposta a cliente perdido.

## O que calcular para cada agência nova

| Indicador | Como calcular | Por que importa |
|---|---|---|
| Frota por categoria e por modelo | contagem em `frota_t0.csv` | define quem pode atender quem |
| Contratos por categoria | contagem em `contratos_publicos.csv` | peso de cada categoria na nota |
| **Folga por categoria** | frota da categoria − máx. de carros fora ao mesmo tempo (contratos + frota em contrato em T0) | folga ≤ 1 → categoria crítica |
| SOC médio de volta por categoria | `km_devolucao ÷ autonomia` (média ponderada pelos modelos da frota daquela categoria) | quanto cada volta precisa carregar |
| kWh por recarga por categoria | `(80 − SOC_volta)/100 × bateria` | carga de energia por categoria |
| Teto de potência DC útil por modelo | máximo da curva DC entre 0 e 80% | se DC rápido serve para essa frota |
| Potência AC por modelo | valor da curva AC (é plana até ~90%) | se AC-11/AC-22 rende mais que AC-7 |
| kWh/km por modelo | `bateria ÷ autonomia` | o mesmo km de volta dá SOCs diferentes |

Leituras que derivam disso:

- Categoria com **folga zero e sem upgrade possível** (a mais alta) → candidata a `prioridade = proxima_retirada`.
- Frota dominada por modelos com **DC baixo** (≤ 30 kW) → DC-30 basta; DC-60/120 desperdiça.
- Frota com modelos de **AC 11 kW** → AC-11/AC-22 vale mais que AC-7; sem eles, AC-11 = AC-7.

## Exemplo trabalhado: Bangkok

Catálogo do kit de Bangkok:

| Modelo | Cat. (rank) | Bateria | Autonomia | AC curva | DC pico curva | DC ficha |
|---|---|---:|---:|---:|---:|---:|
| Renault Kwid E-Tech | Bronze (1) | 26,8 | 185 | 7,4 | 26,9 | 30 |
| JAC E-JS1 | Bronze (1) | 31,4 | 181 | 6,6 | 19,2 | 20 |
| Geely EX2 Pro | Prata (2) | 39,0 | 289 | 6,6 | 72,6 | 80 |
| BYD Dolphin Mini GS | Prata (2) | 38,9 | 280 | 6,6 | 38,1 | 40 |
| MG4 Urban Comfort | Ouro (3) | 43,0 | 299 | 11,0 | 80,0 | 80 |
| BYD Dolphin GS | Ouro (3) | 44,9 | 291 | 7,0 | 58,9 | 60 |
| BYD Dolphin Plus | Diamante (4) | 60,5 | 427 | 11,0 | 79,6 | 80 |
| Leapmotor B10 BEV | Diamante (4) | 56,2 | 288 | 11,0 | 140,0 | 140 |

Indicadores de Bangkok:

| Categoria | Frota | Contratos | Máx. fora | Folga | SOC volta | kWh/recarga |
|---|---:|---:|---:|---:|---:|---:|
| Bronze | 32 | 105 | 29 | 3 | 39% | 11,9 |
| Prata | 20 | 65 | 19 | 1 | 36% | 17,0 |
| Ouro | 21 | 77 | 18 | 3 | 38% | 18,3 |
| Diamante | 7 | 24 | 7 | **0** | 24% | 32,7 |

Em Bangkok, Diamante é a categoria crítica, Bronze não aproveita DC acima de 30 kW, e só 3 modelos usam AC de 11 kW.

**Ao abrir Istanbul, Hanoi e as demais, refazer as duas tabelas acima com os arquivos da agência** antes de qualquer decisão.
