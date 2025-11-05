from invalidate import createInvalidatePipeline

def lambda_handler(event, context):
    return createInvalidatePipeline(event, context)
