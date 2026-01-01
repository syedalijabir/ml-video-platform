resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.system_key}/api"
  retention_in_days = 7
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-api-logs"
    }
  )
}

resource "aws_iam_role" "api_task_role" {
  name = "${local.system_key}-api-task-role"
  
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

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${local.system_key}-api-task-policy"
  role = aws_iam_role.api_task_role.id
  
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
        Resource = [
          aws_s3_bucket.videos.arn,
          "${aws_s3_bucket.videos.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.processing_queue.arn
      }
    ]
  })
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.system_key}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = "1024"
  memory                  = "2048"
  execution_role_arn      = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.api_task_role.arn
  
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name  = "api"
      image = "${var.account_id}.dkr.ecr.us-west-2.amazonaws.com/ml-video-platform/api:${var.api_container_tag}"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "APP_NAME"
          value = "ML Video Platform API"
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
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
      
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-api-task"
    }
  )
}

resource "aws_lb" "lb" {
  name               = "${local.system_key}-alb"
  internal           = false
  load_balancer_type = "application"

  enable_http2               = true
  enable_deletion_protection = false
  preserve_host_header       = true
  
  security_groups = [
    aws_security_group.alb.id
  ]
  subnets = module.vpc.public_subnets
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-alb"
    }
  )
}

resource "aws_lb_target_group" "api" {
  name        = "${local.system_key}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"
  load_balancing_algorithm_type = "least_outstanding_requests"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher            = "200"
    path               = "/health"
    port               = "traffic-port"
    protocol           = "HTTP"
    timeout            = 5
    unhealthy_threshold = 3
  }
  
  deregistration_delay = 30
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-api-tg"
    }
  )
}

resource "aws_lb_listener" "https" {
  depends_on = [
    aws_lb.lb,
    aws_lb_target_group.api,
    aws_acm_certificate_validation.cert
  ]
  load_balancer_arn = aws_lb.lb.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate_validation.cert.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http" {  
  depends_on = [
    aws_lb.lb,
    aws_lb_target_group.api
  ]
  load_balancer_arn = aws_lb.lb.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_ecs_service" "api" {
  name            = "${local.system_key}-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  propagate_tags  = "SERVICE"
  
  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
    
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-api-service"
    }
  )
}