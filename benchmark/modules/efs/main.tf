data "aws_region" "current" {}

resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

resource "random_integer" "random" {
  min = 0
  max = 255
}

locals {
  prefix = "benchmark-efs-${random_string.random.result}"
}

#
# Lambda
#

module "lambda" {
  source = "../base"

  src    = "${path.module}/source"
  prefix = local.prefix

  environment_variables = {
    EFS_FILE_SYSTEM_ID = aws_efs_file_system.efs.id
  }

  file_system_arn              = aws_efs_access_point.efs_access_point.arn
  file_system_local_mount_path = "/mnt/efs"

  vpc_security_group_ids = [aws_security_group.lambda_security_group.id]
  vpc_subnet_ids         = [aws_subnet.subnet.id]
}

#
# Additional resources
#

resource "aws_security_group" "security_group" {
  name   = "${local.prefix}-security-group"
  vpc_id = aws_vpc.vpc.id
}

resource "aws_vpc" "vpc" {
  cidr_block           = "10.${random_integer.random.result}.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_internet_gateway" "internet_gateway" {
  vpc_id = aws_vpc.vpc.id
}

resource "aws_subnet" "subnet" {
  cidr_block        = "10.${random_integer.random.result}.0.0/24"
  vpc_id            = aws_vpc.vpc.id
  availability_zone = "${data.aws_region.current.name}a"
}

resource "aws_subnet" "public_subnet" {
  cidr_block        = "10.${random_integer.random.result}.1.0/24"
  vpc_id            = aws_vpc.vpc.id
  availability_zone = "${data.aws_region.current.name}a"
}

resource "aws_route_table" "route_table" {
  vpc_id = aws_vpc.vpc.id
}

resource "aws_route_table" "route_table_public" {
  vpc_id = aws_vpc.vpc.id
}

resource "aws_route_table_association" "route_table_association" {
  subnet_id      = aws_subnet.subnet.id
  route_table_id = aws_route_table.route_table.id
}

resource "aws_route_table_association" "route_table_association_public" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.route_table_public.id
}

resource "aws_efs_file_system" "efs" {
  creation_token         = local.prefix
  availability_zone_name = "${data.aws_region.current.name}a"
}

resource "aws_efs_mount_target" "efs_mount_target" {
  file_system_id = aws_efs_file_system.efs.id
  subnet_id      = aws_subnet.subnet.id
  security_groups = [
    aws_security_group.security_group.id
  ]
}

resource "aws_security_group" "lambda_security_group" {
  name   = "${local.prefix}-lambda-security-group"
  vpc_id = aws_vpc.vpc.id
}

resource "aws_efs_access_point" "efs_access_point" {
  file_system_id = aws_efs_file_system.efs.id

  posix_user {
    gid = "1000"
    uid = "1000"
  }

  root_directory {
    path = "/export"
    creation_info {
      owner_gid   = "1000"
      owner_uid   = "1000"
      permissions = "755"
    }
  }
}

resource "aws_security_group_rule" "efs_security_group_rule" {
  security_group_id = aws_security_group.security_group.id

  type                     = "ingress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.lambda_security_group.id
}

resource "aws_security_group_rule" "lambda_security_group_rule" {
  security_group_id = aws_security_group.lambda_security_group.id

  type        = "egress"
  from_port   = 0
  to_port     = 0
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "lambda_security_group_rule_2" {
  security_group_id = aws_security_group.lambda_security_group.id

  type        = "ingress"
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

resource "aws_eip" "eip" {}

resource "aws_nat_gateway" "nat_gateway" {
  allocation_id = aws_eip.eip.id
  subnet_id     = aws_subnet.public_subnet.id
}

resource "aws_route" "route_nat" {
  route_table_id         = aws_route_table.route_table.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat_gateway.id
}

resource "aws_route" "route_igw" {
  route_table_id         = aws_route_table.route_table_public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.internet_gateway.id
}
