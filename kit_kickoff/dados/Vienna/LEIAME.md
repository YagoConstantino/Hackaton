# Kit de dados — Vienna

Dados fictícios do cenário. Veículos e curvas de recarga vêm de dados públicos de mercado e não representam a frota de nenhuma empresa. Custos de obra (pontos) e pesos da nota só são divulgados em H4 (anexo H4 e `GET /catalogo`).

Tempos em `contratos_publicos.csv` e `frota_t0.csv`: ISO 8601 (fuso do cenário). T0 = 2049-10-17T18:00. Potência em kW, energia em kWh, autonomia em km, SOC em %.

As tabelas em `curvas/*.md` têm 21 linhas (0%, 5%, …, 100%). A potência usada num degrau [5i%, 5i+5%) é a média das linhas i e i+1, com índice `min(19, floor(SOC/5))` — os mesmos 20 valores de `GET /catalogo` (`curvas[modelo].ac` / `.dc`).

| Arquivo | Conteúdo |
|---|---|
| `agencias.md` | vagas elétricas, horário, frota e entrada elétrica existente (kW úteis) de Vienna |
| `contratos_publicos.csv` | contratos de Vienna com retirada nas semanas públicas (1 a 4) |
| `frota_t0.csv` | estado de cada veículo de Vienna em T0 |
| `veiculos.csv` | catálogo de veículos (ficha) |
| `curvas/*.md` | curva de recarga AC/DC de cada modelo, em degraus de 5% de SOC |
| `categorias.csv` | ordem das categorias (`rank` maior = categoria superior) |
| `carregadores.csv` | carregadores instaláveis |
| `entrada_eletrica.csv` | níveis de entrada elétrica |

## Colunas

- `contratos_publicos.csv`: `id`, `categoria` (pedida), `retirada`, `devolucao`, `autonomia_min_retirada_km`, `km_devolucao` (autonomia restante na devolução).
- `frota_t0.csv`: `id`, `modelo`, `categoria`, `situacao` (`em_contrato`, `estoque_pronto` ou `estoque_a_carregar`), `soc_pct` (só no estoque), `devolucao_prevista` e `soc_devolucao_pct` (só em contrato).
- `veiculos.csv`: `modelo`, `bateria_kwh`, `autonomia_km`, `recarga_ac_kw`, `recarga_dc_kw` (pico da ficha; a curva manda), `grupo` (categoria).
- `categorias.csv`: `grupo`, `rank`.
- `carregadores.csv`: `modelo_id`, `modelo`, `tipo` (AC/DC), `potencia_kw`, `saidas`.
- `entrada_eletrica.csv`: `nivel_id`, `descricao`, `kva`, `kw_util`.
