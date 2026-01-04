resource "aws_db_subnet_group" "db" {
  name       = "${local.system_key}-db-subnet-group"
  subnet_ids = module.vpc.private_subnets
  
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-db-subnet-group"
    }
  )
}

resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/${local.system_key}/${var.environment}/database/password"
  description = "Password for RDS database"
  type        = "SecureString"
  value       = random_password.db_password.result

  tags = merge(
    local.common_tags,
    {}
  )
}

resource "aws_ssm_parameter" "db_username" {
  name        = "/${local.system_key}/${var.environment}/database/username"
  description = "Username for RDS database"
  type        = "String"
  value       = "${var.db_username}"

  tags = merge(
    local.common_tags,
    {}
  )
}

resource "aws_ssm_parameter" "db_name" {
  name        = "/${local.system_key}/${var.environment}/database/name"
  description = "Name for RDS database"
  type        = "String"
  value       = "${var.db_name}"

  tags = merge(
    local.common_tags,
    {}
  )
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.system_key}-db"
  engine         = "postgres"
  engine_version = "15.15"
  
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  
  db_name  = aws_ssm_parameter.db_name.value
  username = aws_ssm_parameter.db_username.value
  password = aws_ssm_parameter.db_password.value
  
  db_subnet_group_name = aws_db_subnet_group.db.name
  vpc_security_group_ids = [
    aws_security_group.rds.id
  ]
    
  performance_insights_enabled = false
  
  deletion_protection = false
  skip_final_snapshot = true
  final_snapshot_identifier = null
  delete_automated_backups = true
    
  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-db"
    }
  )
}
