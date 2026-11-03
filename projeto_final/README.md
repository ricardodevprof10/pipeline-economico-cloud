
# Projeto integrador de Engenharia de Dados

## Visão geral

Pipeline de dados econômicos desenvolvido como
projeto integrador de um curso de Engenharia de Dados.

O projeto demonstra ingestão, transformação,
validação, armazenamento analítico e automação.

Os dados utilizados neste laboratório são sintéticos.

## Tecnologias

- Python 3.11
- pandas
- Apache Parquet
- PyArrow
- PostgreSQL
- Neon
- GitHub Actions
- pytest

## Arquitetura

Dados sintéticos
    |
    v
Bronze (Parquet)
    |
    v
Silver (Parquet)
    |
    v
Gold (Parquet)

A camada Silver também é carregada no PostgreSQL.

## Camadas

### Bronze

Armazena os registros originais.

Resultado esperado: 11 registros.

### Silver

Aplica validação, padronização e remoção
de registros inválidos e duplicados.

Resultado esperado: 8 registros.

### Gold

Produz indicadores econômicos agregados por ano.

Resultado esperado: 2 registros.

## PostgreSQL

O pipeline utiliza o schema:

projeto_integrador

Tabelas:

- indicadores
- execucoes

A tabela indicadores utiliza chave composta
por codigo_pais e ano.

O carregamento utiliza ON CONFLICT para
evitar duplicações de indicadores.

## Segurança

A execução com banco é restrita ao
ambiente staging.

A conexão utiliza:

- DATABASE_URL
- NEON_STAGING_HOST
- AMBIENTE

As credenciais são fornecidas pelo
GitHub Environment staging.

Não armazenar credenciais no repositório.

## Testes

Os testes automatizados verificam:

- Integridade da camada Bronze
- Qualidade da camada Silver
- Ausência de duplicidades
- Agregações da camada Gold
- Detecção de resultados incorretos
- Leitura dos arquivos Parquet

Workflow:

Validar projeto final

## Execução integrada

Workflow:

Projeto integrador Engenharia de Dados

A execução integrada utiliza o banco
PostgreSQL do ambiente staging.

## Resultados esperados

Bronze: 11 registros

Silver: 8 registros

Gold: 2 registros

Indicadores persistidos e verificados: 8

## Relatórios

O pipeline gera:

projeto_final/resultados/relatorio_integrador.json

O GitHub Actions publica os arquivos
e relatórios como artefatos.

## Limitações

- Os dados são sintéticos.
- Não existe ingestão de API externa neste laboratório.
- Os arquivos Parquet são armazenados temporariamente
  como artefatos do GitHub Actions.
- O laboratório não implementa um Lakehouse
  transacional completo.
- Os testes unitários não substituem
  os testes de integração com PostgreSQL.

## Evoluções futuras

- Ingestão de dados econômicos reais
- Armazenamento de objetos em nuvem
- Particionamento de arquivos
- Cargas incrementais
- Monitoramento centralizado
- Integração com dashboards analíticos
