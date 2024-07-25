#!/bin/bash

# Inicializar OpenSearch
awslocal opensearch create-domain --domain-name test-db

# Inicializar S3
awslocal s3api create-bucket --bucket test-bucket

# Inicializar SQS
awslocal s3api create-bucket --bucket sqs-bucket
awslocal sqs create-queue --queue-name test-sqs-queue.fifo --attributes FifoQueue=true,ContentBasedDeduplication=true

# Inicializar SES
awslocal ses verify-email-identity --email-address no-reply@local-env.com --region us-east-1

awslocal ses get-identity-verification-attributes --identities no-reply@local-env.com
