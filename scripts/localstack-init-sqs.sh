#!/usr/bin/env bash
set -euo pipefail

awslocal sqs create-queue --queue-name runtime-observer-ingest-dlq >/dev/null
DLQ_ARN="arn:aws:sqs:${AWS_DEFAULT_REGION:-us-east-1}:000000000000:runtime-observer-ingest-dlq"
awslocal sqs create-queue \
  --queue-name runtime-observer-ingest \
  --attributes "RedrivePolicy={\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"5\"},VisibilityTimeout=30,MessageRetentionPeriod=1209600" >/dev/null

echo "Runtime Observer LocalStack SQS queues created"
