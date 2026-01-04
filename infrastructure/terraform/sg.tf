resource "aws_security_group" "alb" {
  name        = "${local.system_key}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description      = "HTTP IPv6"
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    ipv6_cidr_blocks = ["::/0"]
  }

  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    description      = "HTTPS IPv6"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    ipv6_cidr_blocks = ["::/0"]
  }
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-alb-sg"
    }
  )
}

resource "aws_security_group" "api" {
  name        = "${local.system_key}-api-sg"
  description = "Security group for API ECS tasks"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    ipv6_cidr_blocks = ["::/0"]
  }
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-api-sg"
    }
  )
}

resource "aws_security_group" "rds" {
  depends_on = [
    aws_security_group.api,
    aws_security_group.worker
  ]
  name        = "${local.system_key}-rds-sg"
  description = "Security group for RDS"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [
        aws_security_group.api.id,
        aws_security_group.worker.id
    ]
  }
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-rds-sg"
    }
  )
}

resource "aws_security_group" "worker" {
  name        = "${local.system_key}-worker-sg"
  description = "Security group for ECS worker tasks"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-worker-sg"
    }
  )
}

resource "aws_security_group" "vpc_endpoint" {
  depends_on = [
    aws_security_group.api,
    aws_security_group.worker
  ]
  name        = "${local.system_key}-vpc-endpoint-sg"
  description = "Security group for VPC endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTPS from API tasks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    security_groups = [aws_security_group.api.id]
  }
  
  ingress {
    description = "HTTPS from Worker tasks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    security_groups = [aws_security_group.worker.id]
  }

  ingress {
    description = "TLS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    ipv6_cidr_blocks = [module.vpc.vpc_ipv6_cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = {
    Name = "${local.system_key}-vpc-endpoint-sg"
  }
}
