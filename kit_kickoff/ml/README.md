# ml/ — modelos de ML sobre o motor

Genérico para qualquer agência em `dados/<Agencia>/`. Rótulos vêm do `kickoff/motor.py` (validado contra o juiz).
Documentação completa: `analise/07_modelos_ml.md`.

```bash
pip install -r ml/requirements.txt
python3 -m unittest testes.test_ml -v                       # testes (todas as agências + agência sintética)
python3 -m ml.rodar Istanbul --amostras 300 --cenarios 5    # -> ml/saida/Istanbul/relatorio.md
python3 -m ml.rodar --todas --amostras 200
python3 -m ml.rodar Istanbul --entradas existente           # só a entrada atual (padrão: auto = explora B3/A4)
```

O relatório traz (1) os melhores candidatos com a entrada atual e (2) a melhor configuração **para cada limite
de potência** (b3_75, A4 com 60…270 kW de demanda), com e sem `evitar_ponta`. Recomendações excluem
`menor_soc` + `divisao=prioridade` até essa combinação bater com o juiz (`--incluir-nao-validadas` para incluir).

| Módulo | Faz |
|---|---|
| `features.py` | tabelas de modelos (curvas, tempos por carregador), contratos, sessões de energia (rótulo), dias, ficha da agência |
| `energia.py` | energia por contrato e por dia (física × Ridge × GBM, validação por semana), perfil semanal, potência sem limite |
| `nao_supervisionado.py` | KMeans de curvas / contratos / dias, IsolationForest de anomalias |
| `carregadores.py` | combinações, dataset de simulações, surrogate GBM, Pareto, recomendação confirmada no motor (+ semanas reamostradas) |
| `sintetico.py` | agência sintética (`python3 -m ml.sintetico Bangkok Nova --escala 4 --vagas 4 --horario 24h`) e reamostragem de semanas |
| `rodar.py` | executa tudo e grava relatório + CSVs + `submissoes_candidatas.json` |

Depois de H4: `python3 baixar_agencias.py --catalogo` grava `dados/catalogo.json`; o `rodar` passa a ordenar pela nota estimada.
