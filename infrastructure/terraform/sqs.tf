# SQS Queue for processing jobs
resource "aws_sqs_queue" "processing_queue" {
  name                       = "${local.system_key}-processing-queue"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400  # 1 day
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 900    # 15 minutes (Lambda timeout)
  
  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.processing_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-processing-queue"
    }
  )
}

# Dead Letter Queue
resource "aws_sqs_queue" "processing_dlq" {
  name                       = "${local.system_key}-processing-dlq"
  message_retention_seconds  = 1209600  # 14 days
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-processing-dlq"
    }
  )
}

# SQS Queue Policy
resource "aws_sqs_queue_policy" "processing_queue" {
  queue_url = aws_sqs_queue.processing_queue.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaReceive"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action   = "sqs:*"
        Resource = aws_sqs_queue.processing_queue.arn
      }
    ]
  })
}