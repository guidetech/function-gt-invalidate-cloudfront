# Lambda Function: Invalidate CloudFront

AWS Lambda function que invalida caminhos específicos de uma distribuição CloudFront como parte de um workflow do AWS CodePipeline.

## Descrição

Esta função é executada como uma ação customizada no CodePipeline e cria uma invalidação no CloudFront para arquivos estáticos especificados. É útil para garantir que o cache do CloudFront seja atualizado após novos deploys, forçando a distribuição a buscar os arquivos mais recentes da origem.

## Arquitetura

### Arquivos

- **[lambda_function.py](lambda_function.py)** - Entry point do Lambda, delega para a função principal
- **[invalidate.py](invalidate.py)** - Contém a lógica principal de invalidação do CloudFront

### Fluxo de Execução

1. Lambda é invocado pelo CodePipeline
2. **Valida a estrutura do evento** e extrai o job ID
3. Extrai o Distribution ID dos parâmetros do job (`UserParameters`)
4. **Valida o Distribution ID** (não vazio, formato correto)
5. **Cria invalidação no CloudFront** para os caminhos especificados
6. **Registra métricas** (invalidation ID, quantidade de caminhos, tempo de execução)
7. Reporta sucesso ou falha de volta ao CodePipeline

### Caminhos Invalidados

A função invalida os seguintes arquivos estáticos:
- `/index.html`
- `/main.js` e `/main.js.map`
- `/polyfills.js` e `/polyfills.js.map`
- `/runtime.js` e `/runtime.js.map`
- `/common.js` e `/common.js.map`
- `/styles.css`

## Integração com AWS

### Serviços Utilizados

- **AWS CodePipeline** - Trigger e notificação de status
- **Amazon CloudFront** - Invalidação de cache
- **AWS Lambda** - Execução da função

### Estrutura do Evento

A função espera um evento do CodePipeline com a seguinte estrutura:

```json
{
  "CodePipeline.job": {
    "id": "job-id",
    "data": {
      "actionConfiguration": {
        "configuration": {
          "UserParameters": "E1234567890ABC"
        }
      }
    }
  }
}
```

## Permissões IAM Necessárias

A função Lambda precisa das seguintes permissões:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateInvalidation"
      ],
      "Resource": "arn:aws:cloudfront::ACCOUNT_ID:distribution/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codepipeline:PutJobSuccessResult",
        "codepipeline:PutJobFailureResult"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Deploy

### Pré-requisitos

- Python 3.x
- AWS CLI configurado
- Permissões para criar/atualizar funções Lambda

### Criar o Pacote de Deploy

```bash
# Criar o arquivo zip com as dependências
zip -r function.zip lambda_function.py invalidate.py
```

### Deploy via AWS CLI

```bash
# Criar a função Lambda
aws lambda create-function \
  --function-name gt-invalidate-cloudfront \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip

# Atualizar função existente
aws lambda update-function-code \
  --function-name gt-invalidate-cloudfront \
  --zip-file fileb://function.zip
```

### Deploy via Infrastructure as Code

Recomenda-se usar Terraform, CloudFormation ou AWS SAM para gerenciar o deploy de forma automatizada.

## Tratamento de Erros

A função possui um sistema robusto de tratamento de erros:

### Validações Preventivas

- **Estrutura do evento**: Verifica se o evento possui a estrutura esperada do CodePipeline
- **Job ID**: Valida se o ID do job está presente
- **Distribution ID**: Valida se o ID não está vazio ou com espaços inválidos

### Níveis de Tratamento

1. **ClientError (boto3)** - Captura erros específicos do AWS SDK
   - Identifica códigos de erro (InvalidArgument, NoSuchDistribution, etc.)
   - Mensagens de erro estruturadas com código e descrição

2. **ValueError** - Captura erros de validação
   - Evento malformado
   - Distribution ID não encontrado
   - Parâmetros inválidos

3. **Exception genérica** - Captura qualquer outro erro não previsto
   - Stack trace completo nos logs
   - Mensagem de erro serializada corretamente

Todos os casos reportam a falha ao CodePipeline via `put_job_failure_result()` com mensagens descritivas.

## Desenvolvimento

### Estrutura do Código

```
function-gt-invalidate-cloudfront/
├── lambda_function.py    # Handler principal
├── invalidate.py        # Lógica de invalidação CloudFront
├── CLAUDE.md           # Documentação para Claude Code
└── README.md           # Este arquivo
```

### Logs

A função utiliza o módulo `logging` do Python para gerar logs estruturados no CloudWatch Logs:

**Logs de Sucesso:**
```
[INFO] Evento recebido do CodePipeline
[INFO] Iniciando invalidação do CloudFront: E1234567890ABC
[INFO] Invalidação criada com sucesso: I2EXAMPLE12345
[INFO] Invalidação concluída com sucesso em 1.23 segundos
```

**Logs de Erro:**
```
[ERROR] Erro do AWS SDK: NoSuchDistribution - The specified distribution does not exist
```

**Informações Registradas:**
- Evento completo recebido do CodePipeline
- Distribution ID sendo processado
- Invalidation ID gerado pelo CloudFront
- Quantidade de caminhos invalidados
- Tempo total de execução
- Stack trace completo em caso de erro

## Monitoramento

### Métricas do Lambda

Métricas importantes para monitorar no CloudWatch:

- **Invocações** - Número de execuções
- **Erros** - Falhas na execução
- **Duração** - Tempo de execução
- **Throttles** - Limitações de concorrência

### Métricas Customizadas

A função retorna um objeto com métricas detalhadas:

```json
{
  "statusCode": 200,
  "distribution_id": "E1234567890ABC",
  "invalidation_id": "I2EXAMPLE12345",
  "paths_invalidated": 10,
  "execution_time": 1.23
}
```

Estas métricas também são registradas nos logs e podem ser extraídas via CloudWatch Logs Insights:

```sql
fields @timestamp, distribution_id, invalidation_id, paths_invalidated, execution_time
| filter ispresent(invalidation_id)
| sort @timestamp desc
```

### Alertas Recomendados

- **Taxa de erro > 5%**: Indica problemas recorrentes
- **Duração > 30 segundos**: Pode indicar problemas de rede ou API
- **Falhas de validação**: Distribution ID inválido ou não encontrado

## Considerações de Segurança

### Validações de Segurança Implementadas

✅ **Validação de input**: Distribution ID não pode estar vazio ou conter apenas espaços
✅ **Logs auditáveis**: Todas as operações são registradas no CloudWatch para auditoria
✅ **Mensagens de erro descritivas**: Facilita troubleshooting sem expor informações sensíveis
✅ **Caminhos fixos**: Lista de caminhos é fixa no código, evitando invalidações arbitrárias

### Limitações do CloudFront

- **Quota de invalidações**: AWS permite 1.000 caminhos por mês gratuitamente, depois cobra por adicional
- **Caminhos com wildcard**: Usar `/*` conta como um caminho, mas invalida tudo (não recomendado para produção)
- **Tempo de propagação**: Invalidações podem levar 10-15 minutos para completar

## Melhorias Implementadas

### Versão 2.0 (Atual)

- ✅ Logging estruturado com módulo `logging` do Python
- ✅ Validação de estrutura do evento do CodePipeline
- ✅ Tratamento robusto de erros com mensagens descritivas
- ✅ Métricas de observabilidade (invalidation ID, tempo de execução)
- ✅ Clientes boto3 criados dentro da função (evita conexões stale)
- ✅ Retorno estruturado para facilitar testes
- ✅ Indentação consistente em todo o código
- ✅ Correção do caminho `/common.js.map` (estava `/common.js.`)

### Versão 1.0 (Inicial)

- Funcionalidade básica de invalidação de CloudFront
- Integração com CodePipeline

## Contato

Guide Tech Solutions
Guilherme Vilela - guilherme.vilela@guidetech.com.br