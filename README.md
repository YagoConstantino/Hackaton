# Análise do projeto — Hackathon Recarga Inteligente

Documentação de contexto e análise. **Cada agência traz seus próprios CSVs e curvas**, então os docs 01–04 descrevem o método e as fórmulas de forma genérica, com Bangkok (tutorial) como exemplo trabalhado. Ao liberar uma agência, refazer as tabelas de exemplo com o kit dela.

O motor (`kit_kickoff/kickoff/motor.py`) está completo; os resultados de Bangkok citados aqui saíram dele e valem como decisão depois de validados contra o juiz (`kit_kickoff/validacao/`).

| Arquivo | O que tem |
|---|---|
| `00_visao_geral_hackathon.md` | Os pontos principais do regulamento: objetivo, cronograma, pontuação, m7Coins, Neblina/Clara, eventos, entregáveis |
| `01_agencias_e_dataset.md` | Como as agências funcionam, o que muda entre elas, e a análise completa dos dados de Bangkok (contratos e frota) |
| `02_categorias_e_veiculos.md` | Bronze/Prata/Ouro/Diamante, os 8 modelos, upgrade, folga de frota por categoria |
| `03_curvas_de_carregamento.md` | Como a curva funciona no juiz, tempos de recarga por modelo × carregador, o que isso implica |
| `04_carregadores_entrada_e_ponta.md` | Os 6 carregadores, os 10 níveis de entrada, demanda contratada, horário de ponta, capacidade de Bangkok |
| `05_regras_do_juiz.md` | Resumo operacional das regras que o simulador próprio precisa replicar |
| `06_analise_para_machine_learning.md` | Como enquadrar cada decisão (ponta, entrada, prioridade, divisão, carregadores) e quais modelos usar |

## Conclusões principais

1. **Não existe rótulo nos dados.** Os rótulos para ML vêm do motor próprio. Ele está pronto e roda em ~0,1 s; falta validar contra o juiz.
2. **Nada é fixo por agência.** Categorias, modelos, curvas, carregadores, entradas, vagas e horário são lidos do kit de cada uma. O motor não tem nenhum valor de Bangkok no código.
3. **Em Bangkok, todo carro volta abaixo de 80%**, mas a agência é folgada: no motor, uma única saída DC-30 atende 100% dos contratos. A decisão ali será de custo (H4).
4. **`evitar_ponta = true` é dominante em agências que fecham até as 18h** e têm janela noturna suficiente (regra no doc 04). Em Bangkok, o motor confirma: mesmos clientes, zero kWh na ponta.
5. **A prioridade da fila só importa quando a infraestrutura é escassa**, e a melhor muda com o carregador: simular as três.
6. **Os pesos da nota podem ser inferidos por regressão linear, de graça**, com testes em Bangkok.
