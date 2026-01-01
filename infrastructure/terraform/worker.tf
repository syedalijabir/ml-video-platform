resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.system_key}/worker"
  retention_in_days = 7
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.system_key}-worker-logs"
    }
  )
}

resource "aws_iam_role" "worker_task_role" {
  name = "${local.system_key}-worker-task-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_worker_task_policy" {
  name = "${local.system_key}-worker-task-policy"
  role = aws_iam_role.worker_task_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.videos.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.videos.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.processing_queue.arn
      }
    ]
  })
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.system_key}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = "1024"
  memory                  = "2048"
  execution_role_arn      = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.worker_task_role.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name  = "worker"
      image = "${var.account_id}.dkr.ecr.us-west-2.amazonaws.com/ml-video-platform/worker:${var.api_container_tag}"
      
      essential = true
      
      environment = [
        {
          name  = "APP_NAME"
          value = "ML Video Platform Worker"
        },
        {
          name  = "AWS_REGION"
          value = var.region
        },
        {
          name  = "S3_BUCKET_NAME"
          value = aws_s3_bucket.videos.bucket
        },
        {
          name  = "SQS_QUEUE_URL"
          value = aws_sqs_queue.processing_queue.url
        },
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_ssm_parameter.db_username.value}:${aws_ssm_parameter.db_password.value}@${aws_db_instance.postgres.endpoint}/${aws_ssm_parameter.db_name.value}"
        },
        {
          name  = "MAX_MESSAGES_PER_BATCH"
          value = "1"
        },
        {
          name  = "SQS_WAIT_TIME"
          value = "20"
        },
        {
          name  = "VISIBILITY_TIMEOUT"
          value = "900"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "worker"
        }
      }
      
      healthCheck = {
        command     = ["CMD-SHELL", "python -c 'from worker.ecs_worker import health_check; exit(0 if health_check() else 1)' || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 120  # 2 minutes for model loading
      }
    }
  ])
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.system_key}-worker-task"
    }
  )
}

resource "aws_ecs_service" "worker" {
  name            = "${local.system_key}-worker-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  propagate_tags  = "SERVICE"
  
  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.system_key}-worker-service"
    }
  )
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = 2    # Upper scaling limit
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_queue_depth" {
  name               = "${local.system_key}-worker-queue-depth"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  
  target_tracking_scaling_policy_configuration {
    target_value = 5.0  # Target 5 messages per task
    
    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      
      dimensions {
        name  = "QueueName"
        value = aws_sqs_queue.processing_queue.name
      }
    }
    
    scale_in_cooldown  = 300  # 5 minutes
    scale_out_cooldown = 60   # 1 minute
  }
}

resource "aws_cloudwatch_metric_alarm" "high_queue_depth" {
  alarm_name          = "${local.system_key}-high-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "50"
  alarm_description   = "Alert when SQS queue has more than 50 messages"
  
  dimensions = {
    QueueName = aws_sqs_queue.processing_queue.name
  }
  
  alarm_actions = []
}

# resource "aws_cloudwatch_metric_alarm" "worker_errors" {
#   alarm_name          = "${local.system_key}-worker-errors"
#   comparison_operator = "GreaterThanThreshold"
#   evaluation_periods  = "1"
#   metric_name         = "4XXError"
#   namespace           = "AWS/ECS"
#   period              = "300"
#   statistic           = "Sum"
#   threshold           = "10"
#   alarm_description   = "Alert when worker has more than 10 errors in 5 minutes"
  
#   dimensions = {
#     ServiceName = aws_ecs_service.worker.name
#     ClusterName = aws_ecs_cluster.main.name
#   }
  
#   alarm_actions = []  # Add SNS topic ARN for notifications
# }