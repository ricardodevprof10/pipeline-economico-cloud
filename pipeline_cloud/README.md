# Pipeline econômico na nuvem

Projeto educacional de Engenharia de Dados com
execução remota utilizando GitHub Actions.

## Fonte

World Bank Open Data API

Indicador: NY.GDP.MKTP.CD
Período: 2020-2024

## Arquitetura

API -> Bronze -> Silver -> Gold

## Tecnologias

- Python
- Pandas
- Requests
- Pytest
- GitHub Actions

## Execução local

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python -m src.pipeline
```

## Automação

O workflow está em:

.github/workflows/pipeline.yml

Pode ser iniciado manualmente pelo GitHub Actions
ou por agendamento.

## Resultados

Os arquivos são publicados como artefatos
da execução e ficam disponíveis por um
período limitado.

## Observação

O pipeline é um projeto educacional.
Os dados são fornecidos pelo Banco Mundial.
