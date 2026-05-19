import boto3
import logging
import time

from botocore.exceptions import ClientError

# Configurar logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def createInvalidatePipeline(event, context):
    start_time = time.time()
    cloudfront_client = boto3.client('cloudfront')
    codepipeline_client = boto3.client('codepipeline')

    try:
        logger.info("Evento recebido do CodePipeline", extra={"event": event})

        # Validar estrutura do evento
        if "CodePipeline.job" not in event:
            raise ValueError("Evento inválido: campo 'CodePipeline.job' não encontrado")

        job_id = event['CodePipeline.job'].get('id')
        if not job_id:
            raise ValueError("Evento inválido: 'job id' não encontrado")

        # Extrair distribution ID
        try:
            distribution_id = event["CodePipeline.job"]['data']['actionConfiguration']['configuration']['UserParameters']
        except KeyError as e:
            raise ValueError(f"Evento inválido: não foi possível extrair UserParameters - {str(e)}")

        # Validar distribution ID
        if not distribution_id or not distribution_id.strip():
            raise ValueError("Distribution ID está vazio")

        distribution_id = distribution_id.strip()
        logger.info(f"Iniciando invalidação do CloudFront: {distribution_id}")

        paths = ['/*']

        # Criar invalidação no CloudFront
        response = cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths,
                },
                'CallerReference': job_id
            }
        )

        invalidation_id = response['Invalidation']['Id']
        logger.info(f"Invalidação criada com sucesso: {invalidation_id}")

        # Calcular tempo de execução
        execution_time = time.time() - start_time
        logger.info(f"Invalidação concluída com sucesso em {execution_time:.2f} segundos")

        # Reportar sucesso ao CodePipeline
        codepipeline_client.put_job_success_result(jobId=job_id)

        return {
            'statusCode': 200,
            'distribution_id': distribution_id,
            'invalidation_id': invalidation_id,
            'paths_invalidated': len(paths),
            'execution_time': execution_time
        }

    except ClientError as e:
        error_message = f"Erro do AWS SDK: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        logger.error(error_message, exc_info=True)

        codepipeline_client.put_job_failure_result(
            jobId=event.get('CodePipeline.job', {}).get('id', 'unknown'),
            failureDetails={
                'type': 'JobFailed',
                'message': error_message
            })

        return {
            'statusCode': 500,
            'error': error_message
        }

    except Exception as e:
        error_message = f"Erro inesperado: {str(e)}"
        logger.error(error_message, exc_info=True)

        codepipeline_client.put_job_failure_result(
            jobId=event.get('CodePipeline.job', {}).get('id', 'unknown'),
            failureDetails={
                'type': 'JobFailed',
                'message': error_message
            })

        return {
            'statusCode': 500,
            'error': error_message
        }