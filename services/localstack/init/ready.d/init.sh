#!/bin/bash

SERVICES_DIR=/opt/code/localstack/services

# Inicializar STS
awslocal iam create-role --role-name BasicRole --assume-role-policy-document file://$SERVICES_DIR/sts/assume-rol-policy.json

# Inicializar OpenSearch
awslocal opensearch create-domain --domain-name test-db

# Inicializar S3
awslocal s3api create-bucket --bucket test-bucket

# Inicializar SQS
awslocal s3api create-bucket --bucket sqs-bucket
awslocal sqs create-queue --queue-name test-sqs-queue-01.fifo --attributes FifoQueue=true,ContentBasedDeduplication=true
awslocal sqs create-queue --queue-name test-sqs-queue-02.fifo --attributes FifoQueue=true,ContentBasedDeduplication=true

# Inicializar SES
awslocal ses verify-email-identity --email-address no-reply@local-env.com --region us-east-1
awslocal ses get-identity-verification-attributes --identities no-reply@local-env.com
