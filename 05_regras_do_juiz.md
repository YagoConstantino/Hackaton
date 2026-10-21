# 05 — Regras do juiz (o que o simulador próprio precisa replicar)

Este é o "contrato" do jogo. Sem um motor que bata com o juiz, não há como gerar dados de treino nem economizar m7Coins. O kit de kickoff já traz o laço de eventos, a medição, a validação e a repartição de potência prontos; falta implementar as regras em `motor.py`, em 7 etapas.

## Tempo

- Minutos desde domingo 17/10/2049 00:00. **T0 = 1080** (dom 18:00). Dia = 1440.
- Janela pública: T0 até T0 + 28 dias. As semanas ocultas vêm logo depois.
- O juiz simula o **horizonte completo** e pontua só a janela pedida (o estado da frota no fim do público influencia o começo do oculto).

## Ordem dos eventos no mesmo minuto

**devolução → abertura / início-fim da ponta / eventos → fim de recarga → retirada → fechamento**

Um carro devolvido apto pode sair no mesmo minuto (mas na prática nenhum volta ≥ 80%).

## Devolução

- SOC = `km_devolucao ÷ autonomia_km do modelo × 100`, **nunca acima do SOC de saída**.
- SOC < 80% → entra na fila (registra o instante de entrada). Caso contrário, fica apto.
- Depois: tenta plugar a fila e recalcula as potências.

## Retirada

- Elegível: `rank ≥ pedido` e SOC ≥ 80%.
- Ordem: **menor upgrade → menor SOC → não plugado → menor id (alfabético)**.
- Sem elegível: **cliente perdido**, sem espera.
- Carro plugado que sai é desplugado na hora (e as potências são recalculadas).
- Agência fechada: ninguém retira (todos os contratos já estão em horário aberto).

## Fila e plugar

- Plugar e desplugar **só com a agência aberta**. A recarga continua com ela fechada.
- Tentativa de plugar acontece quando: um carro volta, um carro termina, a agência abre, um carregador volta de evento.
- A cada tentativa a fila é reordenada pela `prioridade`:
  - `menor_soc`: menor **km restante** (`autonomia × SOC`), não menor SOC.
  - `chegada`: FIFO; carros já na fila em T0 empatam e valem pelo id.
  - `proxima_retirada`: o carro cuja próxima reserva compatível (primeiro contrato não retirado com categoria ≤ a do carro) é mais cedo. Sem reserva → fim. Empate: **maior** SOC, depois menor id.
- Último desempate sempre: menor id.
- Plugados ≤ saídas ≤ vagas.

## Escolha do carregador

Entre os carregadores em operação com saída livre, o que daria mais potência ao carro (nominal dividida igualmente com quem já está ali, limitada pela curva de cada um). Ignora limite e `divisao`. Empate: primeiro em ordem alfabética. Não troca depois.

## Potência (recalculada a cada mudança)

1. **Camada 1 — carregador**: a potência nominal é repartida entre os carros dele que ainda carregam, teto na curva do degrau. A forma (igual ou sequencial) segue a `divisao`.
2. **Camada 2 — agência**: o limite (kW útil em B3, demanda contratada em A4/SE) é repartido; o que cada carro recebeu na camada 1 é seu máximo. `igual` → enchimento de água; `prioridade` → sequencial na ordem da prioridade.
3. Ponta com `evitar_ponta`: todos a 0 kW.
4. Carro com SOC ≥ 80% → 0 kW.

Exemplo de referência (6.3.5, limite 40,5 kW, 2× DC-60, Kwid/Geely/JAC/Dolphin GS): `igual` dá 10,125 kW a cada um; `prioridade` dá Kwid 26,6, Geely 13,9, JAC 0, Dolphin 0.

## Fim de recarga

- O carro chega ao fim do degrau → recalcula e agenda o próximo.
- Chegou a 80%: se aberta, despluga e libera a vaga; se fechada, **segura a vaga até a abertura**.
- Na abertura: desplugar quem está parado em 80% e plugar a fila.

## Medição

Energia em janelas de 15 min (`Medidor`). Pico = maior janela × 4. Energia na ponta = soma das janelas seg–sex 18–21h.

## Eventos ao vivo

Etapa 7 do motor. Formato de `params` só é conhecido no anúncio. Vêm de `eventos_ativos` em `GET /status` (só a ocorrência pública; nas ocultas há um equivalente em horário desconhecido).

## Validação contra o juiz

1. Testar em Bangkok (grátis, cooldown 1 min) com `detalhe=completo`.
2. `python comparar.py sub.json resp.json`.
3. Ler a primeira janela "DIVERGE em" para achar onde o motor errou.
4. Repetir com várias políticas e carregadores até `OK: bate com o juiz` em todas.

Recomendação: validar com pelo menos uma configuração de cada "regime" (só AC; DC com limite apertado; `divisao` igual e prioridade; as três prioridades; com e sem `evitar_ponta`). Cada regime exercita regras diferentes.

## Armadilhas prováveis

- Usar SOC em vez de km no `menor_soc`.
- Esquecer o teto do SOC de devolução (não pode passar do SOC de saída).
- Desplugar com a agência fechada.
- Ordem de eventos no mesmo minuto.
- Empate por id em ordenações.
- Recalcular potência na camada 1 só entre carros **que ainda carregam** (os parados em 80% não consomem a parte).
- Arredondamento de tempo de fim de degrau (o juiz usa tempo contínuo).
