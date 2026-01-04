module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "6.5.0"

  name = "${local.system_key}-vpc"
  cidr = var.vpc_cidr
  azs  = [
    "${var.region}a",
    "${var.region}b",
    "${var.region}c"
  ]

  private_subnets = [
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 0),
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 1),
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 2)
  ]

  public_subnets = [
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 3),
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 4),
    cidrsubnet(var.vpc_cidr, var.vpc_network_bits, 5)
  ]

  enable_ipv6                                    = true
  public_subnet_assign_ipv6_address_on_creation  = true
  private_subnet_assign_ipv6_address_on_creation = true
  create_egress_only_igw = true

  private_subnet_ipv6_prefixes  = [0, 1, 2]
  public_subnet_ipv6_prefixes   = [3, 4, 5]

  enable_nat_gateway     = true
  single_nat_gateway     = true
  one_nat_gateway_per_az = false
  enable_vpn_gateway     = false
  enable_dns_hostnames   = true
  enable_dns_support     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.system_key}-vpc"
      CIDR = "${var.vpc_cidr}"
    },
  )
}