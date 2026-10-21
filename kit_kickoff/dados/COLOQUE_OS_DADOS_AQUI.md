# Coloque os dados aqui

1. Baixe o kit de dados da sua agência: `python -m kickoff.api kit Bangkok` (precisa de `GAMEDAY_URL` e `GAMEDAY_TOKEN`), ou pela página `/docs`, ou `GET /agencias/{agencia}/kit`.
2. Se baixou o zip à mão, descompacte **dentro desta pasta**. O zip já traz a pasta com o nome da agência.

Resultado esperado (exemplo com Bangkok):

```
dados/
  Bangkok/
    agencias.md
    contratos_publicos.csv
    frota_t0.csv
    veiculos.csv
    categorias.csv
    carregadores.csv
    entrada_eletrica.csv
    curvas/
      <um .md por modelo de veículo>
    LEIAME.md
  catalogo.json        (opcional, só depois de H4)
```

Com mais de uma agência, cada kit fica na sua pasta (`dados/{Agencia}/`).

`catalogo.json` é a resposta de `GET /catalogo` depois de H4 (traz custos e pesos): `python -m kickoff.api catalogo dados/catalogo.json`. Com ele o simulador calcula a nota.

Confira o carregamento: `python -m kickoff.dados Bangkok`.
