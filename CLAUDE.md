# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AWS Lambda function designed to invalidate specific paths in a CloudFront distribution as part of a CodePipeline workflow. The function is triggered by AWS CodePipeline and receives the target distribution ID via the pipeline's UserParameters.

**Version**: 2.0 (Refactored with enhanced validation, logging, and observability)

## Architecture

**Entry Point**: `lambda_function.py`
- Simple handler that delegates to the main processing function
- Returns the result of the operation for testability

**Core Logic**: `invalidate.py`
- `createInvalidatePipeline(event, context)`: Main function with comprehensive workflow:

  **Validation Phase**:
  1. Validates CodePipeline event structure and extracts job ID
  2. Extracts distribution ID from `event["CodePipeline.job"]['data']['actionConfiguration']['configuration']['UserParameters']`
  3. Validates distribution ID (not empty, properly formatted)

  **Execution Phase**:
  4. Creates CloudFront invalidation for predefined paths using `cloudfront.create_invalidation()`
  5. Tracks execution time using `time.time()`
  6. Captures invalidation ID from response

  **Reporting Phase**:
  7. Logs metrics (invalidation ID, paths count, execution time)
  8. Reports success to CodePipeline via `put_job_success_result(jobId)`
  9. Returns structured response with metrics

**Deployment**:
- No pre-packaged zip file in repository
- Use `zip -r function.zip lambda_function.py invalidate.py` to create deployment package
- Deploy via AWS CLI, Terraform, CloudFormation, or SAM

## AWS Integration

This Lambda integrates with three AWS services:
- **CloudFront**: Uses boto3 client to create invalidations for cache clearing
- **CodePipeline**: Receives job configuration and reports execution status
- **CloudWatch Logs**: Structured logging using Python's `logging` module

Event structure expects CodePipeline job format with distribution ID in:
```
event["CodePipeline.job"]['data']['actionConfiguration']['configuration']['UserParameters']
```

## Invalidation Paths

The function invalidates these specific static files:
- `/index.html` - Main HTML file
- `/main.js`, `/main.js.map` - Main application bundle
- `/polyfills.js`, `/polyfills.js.map` - Browser polyfills
- `/runtime.js`, `/runtime.js.map` - Angular runtime
- `/common.js`, `/common.js.map` - Common shared code
- `/styles.css` - Styles

**Total**: 10 paths (Quantity field matches Items array length)

**Note**: CloudFront charges for paths beyond 1,000/month. Consider using wildcard `/*` for full cache clearing (counts as 1 path but slower propagation).

## Logging and Observability

**Logging Strategy**:
- Uses Python's `logging` module (not `print()`)
- Log level: INFO for normal operations, ERROR for failures
- All logs include contextual information (distribution ID, invalidation ID, timing)
- Stack traces included for exceptions via `exc_info=True`

**Metrics Tracked**:
- Distribution ID being invalidated
- Invalidation ID returned by CloudFront
- Number of paths invalidated (fixed: 10)
- Execution time in seconds
- Structured return value with `statusCode`, `distribution_id`, `invalidation_id`, `paths_invalidated`, `execution_time`

**Log Examples**:
```
[INFO] Evento recebido do CodePipeline
[INFO] Iniciando invalidação do CloudFront: E1234567890ABC
[INFO] Invalidação criada com sucesso: I2EXAMPLE12345
[INFO] Invalidação concluída com sucesso em 1.23 segundos
```

## Error Handling

Comprehensive error handling with three levels:

1. **`ValueError`**: Validation errors
   - Malformed CodePipeline event structure
   - Missing or empty distribution ID
   - Invalid UserParameters format

2. **`ClientError` (boto3)**: AWS SDK errors
   - Extracts error code and message from response
   - Common errors: NoSuchDistribution, InvalidArgument, AccessDenied
   - Reports to CodePipeline with structured error details

3. **Generic `Exception`**: Unexpected errors
   - Catches any unforeseen issues
   - Logs full stack trace
   - Reports to CodePipeline with error message

All error paths:
- Log the error with `logger.error()`
- Call `put_job_failure_result(jobId, failureDetails)`
- Return structured error response (`statusCode: 500`, `error: message`)

## IAM Permissions Required

The Lambda execution role needs:

**CloudFront Permissions**:
- `cloudfront:CreateInvalidation` - Create cache invalidations

**CodePipeline Permissions**:
- `codepipeline:PutJobSuccessResult` - Report success
- `codepipeline:PutJobFailureResult` - Report failure

**CloudWatch Logs Permissions**:
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

## Best Practices Implemented

✅ **No global clients**: `cloudfront_client` and `codepipeline_client` created inside function to avoid connection reuse issues
✅ **Structured logging**: Uses `logging` module with appropriate levels
✅ **Input validation**: Checks event structure and distribution ID before operations
✅ **Metrics tracking**: Captures invalidation ID and measures execution time
✅ **Error messages**: Serializable, descriptive error messages for CodePipeline
✅ **Testability**: Function returns structured response for easier unit testing
✅ **Security**: Fixed path list prevents arbitrary invalidations
✅ **Corrected typo**: Fixed `/common.js.map` path (was `/common.js.` in v1.0)

## Code Style

- Python 3.x compatible
- Consistent 4-space indentation
- Descriptive variable names (snake_case for Python convention)
- Comprehensive comments for each phase
- Uses f-strings for string formatting
- boto3 client interface for CloudFront operations

## CloudFront Invalidation Details

**Invalidation Batch Structure**:
- `Paths.Quantity`: Must match number of items in Items array
- `Paths.Items`: Array of path strings to invalidate
- `CallerReference`: Unique string to prevent duplicate requests (uses CodePipeline job ID)

**Propagation Time**:
- Invalidations typically take 10-15 minutes to complete
- Status can be checked via CloudFront console or API
- Lambda completes immediately after creating invalidation (doesn't wait for propagation)

**Cost Considerations**:
- First 1,000 paths per month are free
- Additional paths: $0.005 per path
- Wildcard `/*` counts as 1 path but invalidates entire distribution

## Common Issues and Solutions

**Issue**: NoSuchDistribution error
**Solution**: Verify distribution ID is correct (format: `E1234567890ABC`)

**Issue**: AccessDenied error
**Solution**: Ensure Lambda execution role has `cloudfront:CreateInvalidation` permission

**Issue**: InvalidArgument - Quantity doesn't match Items
**Solution**: Update `Quantity` field if modifying paths list

**Issue**: Job timeout in CodePipeline
**Solution**: Increase Lambda timeout (function typically completes in 1-2 seconds)
