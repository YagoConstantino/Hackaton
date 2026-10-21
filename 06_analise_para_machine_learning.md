# 06 — Análise para machine learning

## 1. A natureza do problema (ler antes de escolher modelo)

Este não é um problema de aprendizado supervisionado clássico. Três fatos mudam tudo:

1. **Não há rótulos.** Nenhum dado diz "a política certa para esta agência é X". O único "rótulo" possível é a nota que o juiz (ou o nosso simulador) dá a uma configuração.
2. **O juiz é determinístico e as regras são públicas.** Dado o mesmo cenário e a mesma submissão, o resultado é sempre o mesmo e pode ser replicado exatamente. Em vez de "aprender" o juiz a partir de amostras, dá para **reimplementá-lo**.
3. **Poucas unidades reais.** 271 contratos em uma agência, e no total só 7 agências. Não dá para treinar um classificador "agência → decisão" com 7 exemplos.

Portanto o problema é **otimização baseada em simulação** (*simulation-based optimization*), com incerteza sobre as semanas ocultas. O ML entra como ferramenta auxiliar em pontos específicos, sempre alimentado pelo nosso motor:

```
motor fiel ao juiz  →  gerador de cenários  →  simulações em massa  →  modelos substitutos  →  otimização robusta  →  1–2 testes pagos de confirmação
```

## 2. Onde o ML realmente ajuda (5 usos)

| # | Uso | Tipo | Modelo recomendado | Valor |
|---|---|---|---|---|
| A | Inferir os pesos da nota na Neblina | Regressão linear | Mínimos quadrados (OLS), com restrições de sinal | Altíssimo, e é prêmio |
| B | Gerar semanas sintéticas parecidas com as ocultas | Modelagem estatística / generativa | GLM Poisson (chegadas), multinomial (categoria), lognormal (duração), empírica (km) — ou bootstrap por blocos | Alto: é o que dá robustez |
| C | Prever métricas de uma configuração sem simular | Regressão (metamodelo/*surrogate*) | Gradient Boosting (LightGBM/XGBoost) ou Random Forest | Alto em agências grandes; dispensável em Bangkok |
| D | Regras de política explicáveis entre agências | Classificação | Árvore de decisão rasa, regressão logística | Médio: serve para a apresentação e para decidir rápido em agências tardias |
| E | Buscar a melhor configuração | Otimização | Enumeração exaustiva; busca local; Optuna (TPE) ou algoritmo genético | Necessário |

### O que **não** recomendamos

- **Redes neurais / deep learning**: dados escassos, nenhuma estrutura que justifique.
- **Aprendizado por reforço**: a política é um menu fixo de 12 combinações, não um controle contínuo. RL não cabe em 8 horas e não traria ganho.
- **Treinar direto sobre os contratos para "prever a decisão"**: não existe alvo.

## 3. Decisão por decisão

### 3.1 Horário de ponta (`evitar_ponta`) — binária

| | |
|---|---|
| Tipo | Classificação binária |
| Espaço | 2 opções |
| Melhor abordagem | Regra analítica + simular as duas opções |
| ML | Regressão logística ou árvore, só para generalizar o padrão entre agências |
| Features | hora de fechamento nos dias úteis, abre durante 18–21h?, retiradas entre 18–21h, horas entre 21h e a abertura, energia média por carro, kW do limite ÷ vagas |
| Bangkok | **true** (fecha 18h; janela 21h–8h de 11 h é suficiente; nenhuma retirada muda) |

Com só 2 opções, simular as duas é mais barato e mais preciso que qualquer classificador. O classificador vale como **regra de bolso** para a apresentação ("evitar a ponta é dominante quando…").

### 3.2 Entrada elétrica e demanda contratada — ordinal + contínua

| | |
|---|---|
| Tipo | Ordinal (10 níveis) + escalar (30 a teto, passo 10) |
| Melhor abordagem | Simular a **curva perdas × limite** (L de 30 a ~200 kW) e achar o "joelho" |
| ML | Regressão monotônica (isotônica) de `não_atendidos(L)` e `upgrades(L)`; Gradient Boosting com restrição monotônica para prever essa curva em agências novas a partir das features |
| Decisão | Escolher o (entrada, demanda) mais barato que entrega o L ótimo: `min w_obra·custo(entrada) + w_dem·D + w_nao·perdas(L) − …` |
| Features | vagas, kWh/dia, pico de retiradas na abertura, mix de modelos com DC alto, potência nominal instalada |
| Bangkok | **manter b3_45**: o motor atende 100% com uma saída DC-30, então ampliar não tem retorno |

Ponto-chave: o limite só importa se cortar potência **de dia**, quando a rotatividade da vaga salva clientes. À noite a energia sobra.

Atenção ao B3 vs A4: b3_75 tem 67,5 kW **sem custo de demanda**. Um a4_150 com demanda de 70 kW paga obra + 70·w_dem. Depois de H4, comparar diretamente.

### 3.3 Prioridade da fila (`prioridade`) — 3 classes

| | |
|---|---|
| Tipo | Classificação multiclasse |
| Espaço | 3 opções |
| Melhor abordagem | Simular as três em cada configuração candidata |
| ML | Árvore de decisão / Random Forest classifier treinado em agências sintéticas, para entender **quando** cada uma vence |
| Features | folga de frota por categoria (sobretudo Diamante), mix de contratos, desvio entre categorias da fila, dispersão do SOC de volta, razão sessões/vagas |
| Bangkok | com infraestrutura suficiente, as três empatam (0 perdidos). Com infraestrutura escassa, a melhor muda com o carregador: `chegada` com 2× AC-7, `proxima_retirada` com 2× AC-11. **Não há vencedora universal: simular as três** |

Intuição por opção: `proxima_retirada` olha o futuro (contratos) e prioriza quem vai sair; `menor_soc` prioriza quem está mais longe de 80% em km (Diamante vazio, Leapmotor); `chegada` é neutra e só vence se as outras criarem "fome" para algum carro.

### 3.4 Divisão (`divisao`) — binária, com forte interação

| | |
|---|---|
| Tipo | Classificação binária |
| Interação | Só importa quando o limite ou um DC de 2 saídas está saturado |
| Melhor abordagem | Simular as duas junto com a prioridade (6 combinações) |
| Bangkok | hipótese: **prioridade** se houver DC no b3_45 (concentrar potência num carro que sai antes); com só AC, indiferente |

### 3.5 Carregadores — combinatória

| | |
|---|---|
| Tipo | Otimização combinatória com restrição (Σ saídas ≤ vagas) |
| Espaço | 258 combinações em Bangkok; 41 mil com 20 vagas |
| Melhor abordagem em Bangkok | **Enumeração exaustiva** com o motor |
| Melhor abordagem em agências grandes | Regressão *surrogate* (Gradient Boosting) prevendo as métricas a partir de features da configuração, depois busca (Optuna/algoritmo genético) e confirmação com o motor nos top-20 |
| Features da configuração | nº de saídas AC, nº de saídas DC, kW nominal AC e DC totais, kW por saída DC, nº de carregadores de 2 saídas, saídas ÷ vagas, kW nominal ÷ limite |

Resultado do motor em Bangkok: 1× dc_30 ou 1× dc_60x2 atendem 100%; 3× ac_7 perde 1–2. A escolha final entre eles depende só dos custos de obra (H4). Em agências maiores, a regra "alguma capacidade DC para rotatividade diurna, AC para o resto" é o ponto de partida da busca.

## 4. Uso A em detalhe: inferir os pesos na Neblina

A nota é **exatamente linear** nas métricas:

```
nota = w_c·certos + w_u·upgrades − w_n·não_atendidos − w_d·demanda_kW − w_p·kWh_ponta − Σ_k (w_obra·custo_k)·qtd_k − w_obra·custo_entrada
```

Como `certos + upgrades + não_atendidos = N` (fixo), reescrevemos:

```
nota = (w_c + w_n)·certos + (w_u + w_n)·upgrades − w_d·D − w_p·E_ponta − Σ_k β_k·qtd_k − γ_entrada − w_n·N
```

Incógnitas: (w_c+w_n), (w_u+w_n), w_d, w_p, β por tipo de carregador (6), γ por entrada usada, e o intercepto −w_n·N (que identifica w_n, já que N é conhecido). Antes de H4, β_k = w_obra·custo_k é o que importa — não precisamos separar peso de custo.

Fonte das métricas que a Neblina não devolve: certos, upgrades e energia na ponta vêm do **nosso motor** (por isso ele precisa bater com o juiz). A energia na ponta também pode ser lida da série de 15 min do teste `completo`, que em Bangkok é grátis.

Desenho de experimentos em Bangkok (custo zero, cooldown 1 min):

1. **Isolar a ponta**: mesma configuração, só alterna `evitar_ponta`. Em Bangkok os clientes não mudam, então Δnota = w_p·ΔE_ponta.
2. **Isolar a demanda**: entrada A4 com só AC instalado (potência nominal < 50 kW), variando a demanda entre valores que **nunca cortam** (60, 80, 100, 130). A física é idêntica, então Δnota = w_d·ΔD.
3. **Clientes e carregadores**: variar quantidades e tipos de carregador e políticas, e ajustar OLS sobre todas as observações.

Uns 25–40 testes resolvem o sistema com folga. Cuidado: a organização pode ter pesos diferentes por agência, então trate os pesos de Bangkok como **estimativa da estrutura**; os custos de obra (catálogo) devem ser comuns.

## 5. Uso B em detalhe: semanas sintéticas

A nota final é nas semanas ocultas. As 4 semanas públicas mostram volume estável (~68/semana) mas mix variável. Duas opções:

- **Bootstrap por blocos de semana**: recombinar semanas inteiras (preserva correlações dia/hora), com reamostragem de contratos dentro do bloco. Simples e fiel.
- **Modelo generativo**: chegadas por dia×hora ~ Poisson (ou Binomial Negativa se houver sobredispersão); categoria ~ multinomial por dia; duração ~ lognormal por categoria; `km_devolucao` ~ empírica por categoria; devolução "na abertura" com a probabilidade observada (63%).

Uso: avaliar cada configuração em, por exemplo, 20 cenários e escolher pela **média − λ·desvio** ou por um percentil baixo (ex.: P20). Isso troca um pouco de nota esperada por segurança.

## 6. Uso C em detalhe: o dataset de treino do *surrogate*

Uma linha = uma simulação.

| Bloco | Colunas |
|---|---|
| Agência (doc 01) | vagas, horas abertas, fecha antes da ponta, maior intervalo fechado, kWh/dia, contratos/semana, mix, folga por categoria… |
| Configuração | saídas AC/DC, kW nominal AC/DC, limite kW, entrada, demanda, política (one-hot) |
| Cenário | id do bootstrap (para medir variância) |
| **Alvos** | certos, upgrades, não_atendidos, energia_ponta_kWh, pico_kW, energia_kWh |

Prever **as métricas, não a nota**. A nota é montada depois com os pesos vigentes. Como a organização pode mudar pesos durante o dia, isso permite reotimizar sem refazer simulações.

Para ter generalização entre agências com só 7 reais, gerar **agências sintéticas** (variar vagas, frota, horário, volume) a partir das reais.

Orçamento de simulação: o motor leva **~0,1 s por rodada** em Bangkok. 258 combinações × 12 políticas ≈ 3.100 rodadas ≈ 5 min; × 20 cenários ≈ 1,7 h num núcleo, ou ~15 min com 8 processos. Em agências grandes (milhares de combinações), podar: fixar `evitar_ponta` quando a regra do doc 04 o torna dominante, e descartar combinações dominadas.

## 7. Resumo das escolhas de modelo

| Decisão | Problema | Abordagem principal | Modelo de ML auxiliar |
|---|---|---|---|
| Horário de ponta | Classificação binária | Regra + simular 2 | Regressão logística / árvore (explicar) |
| Entrada elétrica | Ordinal | Curva perdas × limite | Regressão isotônica; GBM monotônico |
| Demanda contratada | Regressão / escalar | Busca 1D no joelho da curva | Regressão isotônica |
| Prioridade | Classificação 3 classes | Simular 3 | Árvore / Random Forest classifier |
| Divisão | Classificação binária | Simular 2 (junto com prioridade) | Árvore |
| Carregadores | Combinatória | Enumeração (Bangkok) / surrogate + busca | Gradient Boosting regressor + Optuna/GA |
| Pesos da nota | Regressão linear | OLS sobre testes grátis | — |
| Demanda futura | Modelagem estatística | Bootstrap ou GLM | Poisson / lognormal |

## 8. Riscos

- **Motor infiel**: todo o pipeline herda o erro. Validar em vários regimes antes de gerar dados.
- **Sobreajuste ao público**: escolher pela média em cenários sintéticos, não pela nota pública.
- **Pesos por agência**: a inferência de Bangkok pode não valer para as outras; confirmar com 1 teste em cada agência.
- **Eventos**: uma configuração no limite (ex.: um único DC) pode desabar se ele quebrar. Preferir soluções com redundância quando a perda de nota for pequena.
- **Tempo**: agências que abrem tarde exigem um caminho rápido (regras da árvore + poucos candidatos simulados).

## 9. Próximos passos (quando formos para o código)

1. Completar e validar o motor (etapas 2–7 do `AGENTS.md`) contra o juiz em Bangkok.
2. Medir o tempo de uma simulação.
3. Rodar os experimentos de inferência de pesos em Bangkok.
4. Implementar o gerador de cenários (bootstrap primeiro).
5. Enumerar Bangkok inteiro e validar as hipóteses deste documento.
6. Montar o dataset e o *surrogate* para as agências grandes.
7. Dashboard em cima das séries do motor.
