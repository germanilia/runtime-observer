terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_sqs_queue" "ingest_dlq" {
  name                      = "${var.name_prefix}-ingest-dlq"
  message_retention_seconds = 1209600

  tags = var.tags
}

resource "aws_sqs_queue" "ingest" {
  name                       = "${var.name_prefix}-ingest"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingest_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = var.tags
}

output "ingest_queue_url" {
  value = aws_sqs_queue.ingest.url
}

output "ingest_queue_arn" {
  value = aws_sqs_queue.ingest.arn
}

output "ingest_dlq_url" {
  value = aws_sqs_queue.ingest_dlq.url
}
