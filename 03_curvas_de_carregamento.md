# 03 — Curvas de carregamento

> **Vale para qualquer agência.** As curvas vêm em `dados/<Agencia>/curvas/*.md` e podem mudar de um kit para outro. As regras abaixo (como o juiz lê a curva) são fixas; os números das tabelas são de Bangkok e devem ser recalculados para cada agência.

## Como o juiz usa a curva (regra fixa)

Cada arquivo tem 21 linhas (SOC 0%, 5%, …, 100%) com a potência AC e DC aceita pelo carro.

- Potência **num degrau** [5i%, 5i+5%) = **média das linhas i e i+1**. São 20 degraus (os mesmos 20 valores de `GET /catalogo`, `curvas[modelo].ac/.dc`).
- Índice do degrau: `min(19, floor(SOC/5))`.
- A potência é constante dentro do degrau. O motor agenda um evento a cada troca de degrau.
- Potência real do carro = `min(curva no degrau, parte do carregador, parte do limite da agência)`.
- Sem perdas de conversão (100%); os 90% de eficiência já estão no kW útil da entrada.
- O carro só carrega até **80%** (alvo fixo).

## Fórmula do tempo de recarga

Para ir de `s0` a `s1` num carregador que entrega no máximo `P` kW:

```
tempo = Σ (degraus i entre s0 e s1)  (Δsoc_i / 100) × bateria_kWh / min(P, curva_i) × 60   [min]
```

É exatamente o que o motor faz. Conferência com o regulamento (6.3.2): Dolphin GS 20% → 80% sozinho num DC-60 = **36,7 min**; de 80% a 100% seriam mais 48,9 min.

## Formatos típicos

- **AC**: plana no máximo do carro até ~90%, cai no fim. O tempo é quase linear na energia: `≈ kWh ÷ min(P, AC_carro)`.
- **DC**: sobe, faz platô e cai. Para modelos de DC alto, a potência entre 50% e 80% fica bem abaixo do pico; carro que volta com SOC alto aproveita pouco o DC rápido.

## O que calcular para cada agência nova

1. **Para cada modelo da frota**: tempo de 20→80% e de SOC_médio_de_volta→80% em cada carregador (AC-7, AC-11, AC-22, DC-30, DC-60 sozinho e dividido, DC-120) e com o limite da entrada existente.
2. **Teto DC útil**: maior valor da curva DC entre 0 e 80%. Se ≤ 30 kW, DC-30 basta para esse modelo.
3. **AC útil**: valor da curva AC. Se ≤ 7,4 kW, AC-11 e AC-22 não ajudam esse modelo.
4. **Sessões por vaga por dia**: `horas abertas ÷ tempo médio de recarga` (ponderado pelo mix de devoluções).
5. **Pior caso noturno**: maior tempo de recarga em AC do modelo mais lento a partir do menor SOC de volta. Compara com a janela 21h → abertura (decide `evitar_ponta`, doc 04).

## Exemplo trabalhado: Bangkok

### Tempo de 20% → 80% (sozinho, sem limite), em minutos

| Modelo | kWh | AC-7 | AC-11 | DC-30 | DC-60 (1 carro) | DC-60 (2 carros) | DC-120 (1 carro) | DC a 40,5 kW |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Kwid | 16,1 | 138 | 130 | 37 | 37 | 37 | 37 | 37 |
| JAC | 18,8 | 171 | 171 | 61 | 61 | 61 | 61 | 61 |
| Geely | 23,4 | 213 | 213 | 47 | 25 | 47 | 23 | 35 |
| Dolphin Mini | 23,3 | 212 | 212 | 47 | 38 | 47 | 38 | 38 |
| MG4 | 25,8 | 221 | 141 | 52 | 26 | 52 | 20 | 38 |
| Dolphin GS | 26,9 | 231 | 231 | 54 | 37 | 54 | 37 | 43 |
| Dolphin Plus | 36,3 | 311 | 198 | 73 | 38 | 73 | 33 | 54 |
| Leapmotor | 33,7 | 289 | 184 | 67 | 34 | 67 | 22 | 50 |

(AC-22 com um carro = AC-11, porque nenhum carro aceita mais de 11 kW em AC.)

### Tempo de 40% → 80% (perto do SOC médio de volta, ~37%)

| Modelo | AC-7 | AC-11 | DC-30 | DC-60 (1) | DC-120 (1) | DC a 40,5 kW |
|---|---:|---:|---:|---:|---:|---:|
| Kwid | 92 | 87 | 25 | 25 | 25 | 25 |
| JAC | 114 | 114 | 41 | 41 | 41 | 41 |
| Geely | 142 | 142 | 31 | 17 | 17 | 23 |
| Dolphin Mini | 141 | 141 | 31 | 26 | 26 | 26 |
| MG4 | 147 | 94 | 34 | 17 | 14 | 25 |
| Dolphin GS | 154 | 154 | 36 | 27 | 27 | 30 |
| Dolphin Plus | 207 | 132 | 48 | 26 | 23 | 36 |
| Leapmotor | 193 | 123 | 45 | 23 | 16 | 33 |

### Leituras de Bangkok (confirmadas no motor)

- AC leva 1,5 a 5 h; DC, 15 a 75 min. Uma vaga DC gira 4–8 carros num dia de 10 h; uma AC, 2–4.
- **`ac_11 ×2` e `ac_22x2 ×1` dão resultado idêntico** no motor (mesmos clientes, mesma energia): o AC-22 nunca divide de fato.
- Com o limite de 40,5 kW, um único carro DC rápido já consome quase tudo; dois DC rápidos simultâneos não aceleram.
- À noite e no fim de semana a velocidade não importa: o carro segura a vaga de qualquer jeito ao chegar a 80%. **DC se paga em rotatividade diurna; AC basta para o pernoite.**
- No motor, **um único DC-30 atende 100% dos contratos de Bangkok** (a confirmar contra o juiz). Bangkok é folgada; agências maiores provavelmente não serão.
