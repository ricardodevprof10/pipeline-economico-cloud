# Projeto de Engenharia de Dados — Pipeline Econômico em Nuvem

## Apresentação

Desenvolvimento de um pipeline de Engenharia de Dados utilizando Python, PostgreSQL, Apache Parquet e GitHub Actions, com foco em processamento, qualidade, persistência e automação de dados.

O projeto integrador utiliza dados econômicos sintéticos para demonstrar a implementação de uma arquitetura de processamento em camadas Bronze, Silver e Gold.

## Tecnologias utilizadas

- Python e pandas para transformação de dados.
- Apache Parquet e PyArrow para armazenamento colunar.
- PostgreSQL e Neon para persistência.
- GitHub Actions para automação.
- pytest para testes automatizados.
- Git e GitHub para versionamento e integração contínua.

## Funcionalidades implementadas

- Ingestão de dados estruturados.
- Tratamento de registros inválidos e duplicados.
- Agregação de indicadores econômicos.
- Persistência de dados em PostgreSQL.
- Carregamento idempotente com tratamento de conflitos.
- Registro de execuções para auditoria.
- Validação automatizada de qualidade.
- Geração de relatórios estruturados em JSON.

## Competências demonstradas

Engenharia de Dados, ETL, SQL, modelagem de dados, automação, integração contínua, qualidade de dados, observabilidade e organização de pipelines em nuvem.

## Resultados esperados do laboratório

O projeto processa onze registros sintéticos na camada Bronze, produz oito registros tratados na camada Silver e dois resultados agregados na camada Gold.

A carga PostgreSQL verifica a persistência dos oito indicadores esperados.

Os resultados devem ser confirmados por meio dos testes e workflows automatizados.

## Repositório

https://github.com/ricardodevprof10/pipeline-economico-cloud

## Possibilidades de evolução

A arquitetura poderá ser ampliada para ingestão de APIs econômicas reais, armazenamento de objetos, processamento incremental e integração com sistemas analíticos de maior escala.
