resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  
  route_table_ids = module.vpc.private_route_table_ids
  
  tags = {
    Name = "${local.system_key}-s3-endpoint"
  }
}
