variable "assume_role" {
  description = "The role TF assumes to manage resources on your behalf"
  type = string
}

variable "account_id" {
  description = "AWS account to deploy resources in"
  type = string
}

variable "vpc_cidr" {
  type = string
  default = "172.30.0.0/24"
}

variable "vpc_network_bits" {
  description = "Number of bits reserverd for networks in CIDR"
  type = number
  default = 3
}

variable "environment" {
  type    = string
  default = "demo"
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "mlvp_owner"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "mlvp"
}

variable "api_container_tag" {
  type    = string
}

variable "worker_container_tag" {
  type    = string
}

variable "hosted_zone" {
  type = string
}

variable "tags" {
  description = "A mapping of tags to assign to all resources"
  type        = map(string)
  default     = {}
}
