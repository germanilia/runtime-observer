variable "aws_region" {
  type        = string
  description = "AWS region for the Runtime Observer SQS queues."
  default     = "us-east-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for queue names."
  default     = "runtime-observer"
}

variable "visibility_timeout_seconds" {
  type        = number
  description = "SQS visibility timeout for ingest messages."
  default     = 30
}

variable "message_retention_seconds" {
  type        = number
  description = "How long SQS keeps ingest messages before expiry."
  default     = 1209600
}

variable "max_receive_count" {
  type        = number
  description = "Failed receives before moving a message to the DLQ."
  default     = 5
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to Runtime Observer queues."
  default = {
    Application = "runtime-observer"
    ManagedBy   = "terraform"
  }
}
