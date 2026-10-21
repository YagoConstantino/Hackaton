# Kit de kickoff

Ponto de partida para a equipe construir o seu próprio simulador do juiz e conferir submissões na janela pública sem gastar m7Coins.

## 1. O que é o kit

O kit traz leitores de dados e helpers prontos (validação, curva de carga, divisão de potência, medição em 15 min, nota, cliente da API) que já batem com o juiz, e um motor-esqueleto (`kickoff/motor.py`) com o laço de eventos pronto. As regras de operação (retirada, fila, plug, potência, ponta, eventos) são de vocês: estão nos métodos marcados `# TODO(etapa N)`. Com o motor vazio, todo cliente é perdido (atendimento 0%). O kit é opcional.

## 2. Requisitos e instalação

1. Python 3.10 ou mais novo. Só biblioteca padrão, nada para instalar.
2. Descompacte `kit_kickoff.zip` (baixado em `/docs` ou `GET /kit-kickoff`) e abra um terminal na pasta `kit_kickoff/`.
3. O kit não traz dados de agência. Baixe o zip da agência em `/docs` (ou `GET /agencias/{id}/kit`) e descompacte **dentro de `dados/`**. O zip já traz a pasta com o nome da agência.
   Alternativa: defina `GAMEDAY_URL` e `GAMEDAY_TOKEN` e rode `python -m kickoff.api kit Bangkok`.
4. Resultado esperado:

```
dados/
  Bangkok/
    agencias.md, contratos_publicos.csv, frota_t0.csv, veiculos.csv,
    categorias.csv, carregadores.csv, entrada_eletrica.csv, curvas/*.md
  catalogo.json   (opcional, só depois de H4)
```

Bangkok é a agência tutorial: testes grátis (0 m7Coins, cooldown de 1 min) e não pontua. É o melhor lugar para medir a fidelidade do motor. Detalhes em `dados/COLOQUE_OS_DADOS_AQUI.md`.

## 3. Mapa dos arquivos

| Arquivo | O que faz | Estado |
|---|---|---|
| `simular.py` | Simula submissões na janela pública com o seu motor. Opções: `--dados`, `--catalogo`, `--eventos`, `--series` | pronto |
| `comparar.py` | Compara o seu motor com a resposta salva de `POST /teste` e aponta a primeira janela divergente | pronto |
| `exemplo_submissao.json` | Submissão de exemplo para Bangkok | pronto |
| `dados/` | Onde ficam os kits das agências (e `catalogo.json`) | vazio, vocês preenchem |
| `testes/test_regulamento.py` | Testes dos números do regulamento (divisão, demanda, curva, carga de dados) | pronto |
| `kickoff/tempo.py` | Minutos desde 17/10/2049 00:00, T0, horário de funcionamento, ponta, `texto(t)` | pronto |
| `kickoff/modelo.py` | Dataclasses do cenário | pronto |
| `kickoff/dados.py` | Lê o kit da agência num `Cenario`; resumo por linha de comando | pronto |
| `kickoff/validar.py` | Validação e normalização da submissão (6.2), mesmas mensagens do juiz | pronto |
| `kickoff/potencia.py` | Curva por degrau, `enchimento_agua` (`igual`) e `sequencial` (`prioridade`) | pronto |
| `kickoff/medicao.py` | Janelas de 15 min, métricas e `series` no formato do juiz | pronto |
| `kickoff/nota.py` | Custo de obra e nota (precisa do catálogo pós-H4) | pronto |
| `kickoff/api.py` | Cliente da API (Referer exigido já configurado) | pronto |
| `kickoff/motor.py` | Laço de eventos, estado, retirada, auxiliares de plug | parcial: regras são TODO |

## 4. Primeiro uso

Na pasta do kit, com `dados/Bangkok/` no lugar:

```
python -m kickoff.dados Bangkok
python simular.py exemplo_submissao.json
python -m unittest discover -s testes
```

O que esperar:

- `kickoff.dados`: resumo da agência (vagas, horário, entrada existente, frota e contratos por categoria). Confirma que os dados carregaram.
- `simular.py`: JSON no formato de `POST /teste`. Com o motor vazio: `nao_atendidos` = `contratos`, `atendimento_pct` 0, `energia_kwh` 0 e `nota` `null` com o aviso de catálogo. Isso é normal.
- `unittest`: 11 testes, todos passam (validação, curva e divisão de potência já estão corretas). Sem `dados/Bangkok/`, o teste de carga de dados aparece como ignorado (`skipped=1`).

## 5. Roteiro de evolução

Cada etapa corresponde aos `# TODO(etapa N)` do `motor.py`. Faça na ordem. Escrevam um `unittest` próprio por etapa em `testes/` (ex.: `testes/test_etapa2.py`) com os exemplos numéricos do regulamento e rodem a suíte inteira a cada mudança.

**Etapa 1: dados.** Pronta. `dados.py` e `validar.py` carregam e validam.

**Etapa 2: retirada e devolução, sem recarga.**
- Métodos: `soc_devolucao`, `entrar_patio`, `escolher_carro`, `on_devolucao`.
- Regulamento: 4.1 (devolução em km), 5.1 (escolha do carro), 6.3.1.
- Pronto quando: com uma submissão com carregadores mas ainda sem recarga, só saem clientes atendidos pelo estoque com SOC >= 80% em T0 e por carros devolvidos com SOC >= 80%; toda retirada tem `soc` >= 80 e categoria >= pedida; o exemplo da 6.3.1 (Geely 82%, Dolphin Mini 95% plugado, MG4, JAC) escolhe o carro certo nos três cenários.

**Etapa 3: fila, plug, curva e fim de recarga, sem limite da agência.**
- Métodos: `ordenar_fila` (chegada e menor_soc), `escolher_ponto`, `plugar_fila`, `recalcular_potencias` (camada 1, carregador), `agendar_fim_degrau`, `on_fim_recarga`.
- Regulamento: 5.2, 5.3, 6.3.2, 6.3.3, 6.3.4, 6.3.5 (camada 1).
- Pronto quando: o exemplo da 6.3.2 é reproduzível (Dolphin GS, 44,9 kWh, de 20% a 80% sozinho num DC-60 leva 36,7 min); o exemplo da 6.3.4 escolhe o DC-60; plugados nunca passam das saídas; o atendimento sobe bem acima do da etapa 2.

**Etapa 4: limite da agência e `divisao`.**
- Métodos: `recalcular_potencias` (camada 2), usando `potencia.enchimento_agua` e `potencia.sequencial`; `limite_kw` já vem em `self.limite_kw`.
- Regulamento: 5.3, 6.2 (demanda), 6.3.5, 6.3.7.
- Pronto quando: o exemplo da 6.3.5 bate (limite 40,5: `igual` 10,125 kW cada; `prioridade` Kwid 26,6, Geely 13,9, JAC 0, Dolphin 0; limite 80: 21,18 kW e Kwid 26,6 / Geely 53,4); a soma das potências nunca passa do limite; `pico_kw` <= limite.

**Etapa 5: horário de funcionamento e `evitar_ponta`.**
- Métodos: `on_abertura`, `on_fechamento`, `on_ponta`.
- Regulamento: 5.2, 5.3, 6.3.6.
- Pronto quando: ninguém pluga nem desconecta com a agência fechada, mas a recarga continua; carro que chega a 80% fechado segura a saída até abrir; com `evitar_ponta`, `energia_ponta_kwh` = 0 e os carros seguem plugados; o exemplo da 6.3.6 (MG4, 17:00 a 22:00) reproduz.

**Etapa 6: as três `prioridade`.**
- Métodos: `ordenar_fila` (completar `menor_soc` em km e `proxima_retirada`); a ordem também vale para `divisao: prioridade`.
- Regulamento: 6.3.3.
- Pronto quando: o exemplo da 6.3.3 gera menor_soc A,B,D,C; chegada A,B,C,D; proxima_retirada C,D,B,A.

**Etapa 7: eventos.**
- Métodos: `agendar_eventos`, `on_evento`.
- Regulamento: 11. O significado e o formato de `params` vêm no anúncio de cada evento; salve `eventos_ativos` de `GET /status` num arquivo e passe com `--eventos`.
- Pronto quando: com o evento ativo, `simular.py --eventos` e o `POST /teste` do juiz (mesmo evento) coincidem. Ao voltar um carregador, a fila é replugada.

**Etapa 8: fidelidade com o juiz.**
- Sem métodos novos: ajuste fino comparando com o juiz.
- Regulamento: 12 (API), 9.1 (custos).
- Pronto quando: `comparar.py` imprime `OK: bate com o juiz` em Bangkok para várias submissões e políticas (todas as combinações de `prioridade`, `divisao`, `evitar_ponta`, com e sem limite apertado).

## 6. Conferindo com o juiz

Passo a passo (use Bangkok: grátis).

1. Defina `GAMEDAY_URL` e `GAMEDAY_TOKEN`.
2. Crie `sub.json` (copie `exemplo_submissao.json` e mude carregadores, entrada, política).
3. Peça o teste completo e salve a resposta (traz `series`):

   ```
   python -m kickoff.api teste Bangkok sub.json --completo --salvar resp.json
   ```

4. Compare com o seu motor:

   ```
   python comparar.py sub.json resp.json
   ```

   Com eventos: `--eventos eventos.json`. Outra pasta de dados: `--dados DIR`.

Como ler o relatório:

- Tabela de métricas: `meu`, `juiz` e `diferença`. `<--` marca o que diverge (tolerância 1e-6; 1% em `energia_kwh`).
- Séries de 15 min (`potencia_kw`, `plugados_max`, `fila_max`): mostra a diferença máxima e a **primeira janela divergente** (ex.: `Seg 18/10 09:15`). O erro nasce nessa janela ou pouco antes: olhem o que aconteceu ali (retirada, devolução, fim de recarga, ponta).
- `nao_atendidos_min`: compara só a contagem.
- Última linha: `OK: bate com o juiz` ou `DIVERGE em: ...`. O script sempre sai com código 0.
- `violações no meu motor`: plugados acima das saídas ou saídas acima das vagas.

Isolar regras: varie uma coisa por vez. Sem política (padrão) e entrada B3 para validar escolha de carro e fila; depois `divisao: prioridade`; depois `prioridade` diferentes; depois `evitar_ponta`. Reduzir o limite (entrada menor) isola a etapa 4.

Atenção: Bangkok fecha às 18:00 nos dias úteis, ou seja, a ponta (18:00–21:00) acontece com a agência fechada. Dá para conferir `energia_ponta_kwh` e a recarga com a agência fechada, mas não o caso de plugar durante a ponta (6.3.6). Esse caso só aparece em agências abertas à noite.

Custos: testes em Bangkok custam 0 m7Coins (cooldown de 1 min; teste idêntico a um anterior não gasta nada). Em outras agências, placar custa 20 e completo 50 (30 se o placar já foi pago). Acerte a fidelidade em Bangkok antes de gastar m7Coins nas agências pontuadas. Limite de 20 requisições por minuto por equipe.

## 7. Depois do motor

- Busca de configurações por agência: rodar `simular.py` com uma lista de submissões (um arquivo pode ter uma lista) e escolher a melhor nota. Com `catalogo.json` pós-H4 a nota sai pronta; antes, usem `metricas` (atendimento, pico, energia na ponta).
- Sensibilidade: variar carregadores, entrada, demanda e política e ver o efeito em atendimento e custo.
- Dashboard obrigatório (seção 13.1): `medicao.series(...)` já devolve potência em 15 min, plugados e fila, e `soc_retirada`; `simular.py --series` imprime isso. A cascata de pontos vem de `pontos` (precisa do catálogo).

## 8. Limitações

- Só a janela pública (4 semanas). As semanas ocultas, usadas na nota final, não estão nos dados. Boa nota aqui não garante a mesma nota nelas.
- O kit não é o juiz: é a base para vocês construírem o seu modelo. A fidelidade depende da implementação de vocês.
- A nota só é calculada com `dados/catalogo.json` (`GET /catalogo` depois de H4, pesos e custos).
- `comparar.py` aceita 1% de diferença em `energia_kwh`; as demais métricas e as séries pedem igualdade.
