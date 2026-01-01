resource "aws_ecs_cluster" "main" {
  name = "${local.system_key}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.system_key}-cluster"
    }
  )
}

resource "aws_ecs_cluster_capacity_providers" "capacity_providers" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE_SPOT"
  }
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "${local.system_key}-ecs-execution-role"
  
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

resource "aws_iam_role_policy_attachment" "ecs_execution_role" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
