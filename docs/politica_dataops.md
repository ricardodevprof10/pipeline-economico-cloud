
# Política de DataOps

## Projeto
South America Economic Data Platform

## Objetivo
Garantir alterações seguras e rastreáveis
nos pipelines econômicos.

## Regras de desenvolvimento

1. Criar alterações em branches separadas.
2. Executar testes automatizados.
3. Revisar os resultados do GitHub Actions.
4. Evitar credenciais nos arquivos do projeto.
5. Não modificar o banco de produção nos testes de CI.
6. Registrar falhas e manter relatórios de auditoria.
7. Aprovar as alterações antes do merge.

## Ambientes

Desenvolvimento:
Alterações e testes isolados.

Produção:
Pipeline principal e PostgreSQL Neon.

## Recuperação

Em caso de falha:
- Consultar os logs.
- Identificar o commit responsável.
- Corrigir ou reverter a alteração.
- Executar novamente os testes.
- Validar os dados após a recuperação.
