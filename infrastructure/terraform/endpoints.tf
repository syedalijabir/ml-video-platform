resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = module.vpc.private_route_table_ids

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-s3-endpoint"
    }
  )
}

# Pulling internally to save on NAT traffic costs
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type = "Interface"

  private_dns_enabled = true
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoint.id]

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-ecr-api-endpoint"
    }
  )
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type = "Interface"

  private_dns_enabled = true
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoint.id]

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-ecr-dkr-endpoint"
    }
  )
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type = "Interface"

  private_dns_enabled = true
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoint.id]

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-logs-endpoint"
    }
  )
}

resource "aws_vpc_endpoint" "sqs" {
  vpc_id            =  module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.sqs"
  vpc_endpoint_type = "Interface"

  private_dns_enabled = true
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoint.id]

  tags = merge(
    local.common_tags,
    {
        Name = "${local.system_key}-sqs-endpoint"
    }
  )
}