terraform {
  backend "s3" {
    bucket = "328421278917-terraform-states"
    key    = "e2e-ml.tfstate"
  }

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = ">= 3.0"
    }
  }
}

resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

resource "random_integer" "random" {
  min = 0
  max = 255
}

data "aws_region" "current" {}
data "aws_ecr_authorization_token" "token" {}
data "aws_caller_identity" "current" {}

provider "docker" {
  registry_auth {
    address  = "328421278917.dkr.ecr.us-east-1.amazonaws.com"
    username = data.aws_ecr_authorization_token.token.user_name
    password = data.aws_ecr_authorization_token.token.password
  }
}

locals {
  prefix = "e2e-ml-${random_string.random.result}"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

#
# Lambda
#

# module "lambda" {
#   source = "../../benchmark/modules/base"

#   src    = "${path.module}/source"
#   prefix = local.prefix

#   environment_variables = {
#     BUCKET_NAME = aws_s3_bucket.bucket.id
#   }
# }

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 5.3"

  function_name  = local.prefix
  create_package = false

  timeout                        = 100
  memory_size                    = 4096
  ephemeral_storage_size         = 10240
  reserved_concurrent_executions = 9

  image_uri    = module.docker_image.image_uri
  package_type = "Image"

  # AWS Academy
  create_role = false
  # lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/magisterka-role"
  lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  environment_variables = {
    SOURCE_BUCKET_NAME  = aws_s3_bucket.source.id
    S3_BUCKET_NAME      = aws_s3_bucket.bucket.id
    DYNAMODB_TABLE_NAME = aws_dynamodb_table.table.name
    # REDIS_IP            = aws_instance.redis.private_ip
    # RELAY_IP            = aws_instance.relay.private_ip
    # P2P_IP              = aws_instance.p2p.public_ip
  }

  vpc_security_group_ids = [aws_security_group.lambda_security_group.id]
  vpc_subnet_ids         = [aws_subnet.subnet.id]

  file_system_arn              = aws_efs_access_point.efs_access_point.arn
  file_system_local_mount_path = "/mnt/efs"

  # # Force redeploy
  # hash_extra = "1"
}

module "lambda2" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 5.3"

  function_name  = "${local.prefix}-2"
  create_package = false

  timeout                        = 100
  memory_size                    = 4096
  ephemeral_storage_size         = 10240
  reserved_concurrent_executions = 9

  image_uri    = module.docker_image.image_uri
  package_type = "Image"

  # AWS Academy
  create_role = false
  # lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/magisterka-role"
  lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  environment_variables = {
    SOURCE_BUCKET_NAME  = aws_s3_bucket.source.id
    S3_BUCKET_NAME      = aws_s3_bucket.bucket.id
    DYNAMODB_TABLE_NAME = aws_dynamodb_table.table.name
    # REDIS_IP            = aws_instance.redis.public_ip
    # RELAY_IP            = aws_instance.relay.public_ip
    # P2P_IP              = aws_instance.p2p.public_ip
  }

  # # Force redeploy
  # hash_extra = "1"
}

module "docker_image" {
  source = "terraform-aws-modules/lambda/aws//modules/docker-build"

  create_ecr_repo = true
  ecr_repo        = local.prefix
  # image_tag   = "latest"
  source_path = "source"
  platform    = "linux/amd64"
  ecr_repo_lifecycle_policy = jsonencode({
    "rules" : [
      {
        "rulePriority" : 1,
        "description" : "Keep only the last 2 images",
        "selection" : {
          "tagStatus" : "any",
          "countType" : "imageCountMoreThan",
          "countNumber" : 2
        },
        "action" : {
          "type" : "expire"
        }
      }
    ]
  })
}

#
# Additional resources
#

resource "aws_s3_bucket" "source" {
  bucket        = "${local.prefix}-source"
  force_destroy = true
}

resource "aws_s3_bucket" "bucket" {
  bucket        = local.prefix
  force_destroy = true
}

resource "aws_dynamodb_table" "table" {
  name         = local.prefix
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_security_group" "security_group" {
  name   = "${local.prefix}-security-group"
  vpc_id = aws_vpc.vpc.id
}

resource "aws_vpc" "vpc" {
  cidr_block = "10.${random_integer.random.result}.0.0/16"

  enable_dns_hostnames = true

  tags = {
    Name = local.prefix
  }
}

# internet gateway
resource "aws_internet_gateway" "internet_gateway" {
  vpc_id = aws_vpc.vpc.id
}

resource "aws_subnet" "subnet" {
  cidr_block        = "10.${random_integer.random.result}.0.0/24"
  vpc_id            = aws_vpc.vpc.id
  availability_zone = "${data.aws_region.current.name}a"
}

resource "aws_subnet" "public" {
  cidr_block              = "10.${random_integer.random.result}.1.0/24"
  vpc_id                  = aws_vpc.vpc.id
  availability_zone       = "${data.aws_region.current.name}a"
  map_public_ip_on_launch = true
}

# route table
resource "aws_route_table" "route_table" {
  vpc_id = aws_vpc.vpc.id
}

# public route table
resource "aws_route_table" "public_route_table" {
  vpc_id = aws_vpc.vpc.id
}

# # public route
resource "aws_route" "public_route" {
  route_table_id         = aws_route_table.public_route_table.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.internet_gateway.id
}

# associate route table with subnet
resource "aws_route_table_association" "route_table_association" {
  subnet_id      = aws_subnet.subnet.id
  route_table_id = aws_route_table.route_table.id
}

# associate public route table with public subnet
resource "aws_route_table_association" "public_route_table_association" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public_route_table.id
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

  type                     = "egress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.security_group.id
}

resource "aws_security_group_rule" "lambda_security_group_rule2" {
  security_group_id = aws_security_group.lambda_security_group.id

  type        = "egress"
  from_port   = 0
  to_port     = 0
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]
}

variable "nat_gateway" {
  type    = bool
  default = true
}

# nat gateway

resource "aws_eip" "eip" {
  count = var.nat_gateway ? 1 : 0
}

resource "aws_nat_gateway" "nat_gateway" {
  count = var.nat_gateway ? 1 : 0

  allocation_id = aws_eip.eip[0].id
  subnet_id     = aws_subnet.public.id
}

resource "aws_route" "route_nat" {
  count = var.nat_gateway ? 1 : 0

  route_table_id         = aws_route_table.route_table.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat_gateway[0].id
}

# security group for ec2
resource "aws_security_group" "ec2" {
  name        = local.prefix
  description = local.prefix
  vpc_id      = aws_vpc.vpc.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 12345
    to_port     = 12345
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# resource "aws_instance" "redis" {
#   # Redis AMI
#   # https://bitnami.com/stack/redis/cloud/aws/amis
#   ami                         = data.aws_ami.ubuntu.id
#   instance_type               = "t3.small"
#   subnet_id                   = aws_subnet.public.id
#   vpc_security_group_ids      = [aws_security_group.ec2.id]
#   key_name                    = "karol"
#   associate_public_ip_address = true

#   user_data_replace_on_change = true
#   user_data                   = <<EOF
# #!/bin/bash
# curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys
# export DEBIAN_FRONTEND=noninteractive
# apt update
# apt install -y redis-server
# sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
# systemctl restart redis-server

# EOF

#   tags = {
#     Name = "${local.prefix}-redis"
#   }
# }

# resource "aws_instance" "relay" {
#   # Redis AMI
#   # https://bitnami.com/stack/redis/cloud/aws/amis
#   ami                         = data.aws_ami.ubuntu.id
#   instance_type               = "t3.small"
#   subnet_id                   = aws_subnet.public.id
#   vpc_security_group_ids      = [aws_security_group.ec2.id]
#   key_name                    = "karol"
#   associate_public_ip_address = true

#   user_data_replace_on_change = true
#   user_data                   = <<EOF
# #!/bin/bash
# curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys
# export DEBIAN_FRONTEND=noninteractive
# apt update
# apt install -y python3 python3-pip

# pip3 install --extra-index-url https://dxsxsb220w9y2.cloudfront.net bulletin==0.0.5

# # create systemd unit
# cat <<FILE > /etc/systemd/system/bulletin.service
# [Unit]
# Description=Bulletin
# After=network.target

# [Service]
# Type=simple
# User=ubuntu
# WorkingDirectory=/home/ubuntu
# ExecStart=/usr/bin/python3 -m bulletin relay --host 0.0.0.0 --port 12345
# Restart=on-failure

# [Install]
# WantedBy=multi-user.target
# FILE

# systemctl daemon-reload
# systemctl enable bulletin.service
# systemctl start bulletin.service

# EOF

#   tags = {
#     Name = "${local.prefix}-relay"
#   }
# }

# resource "aws_instance" "p2p" {
#   # Redis AMI
#   # https://bitnami.com/stack/redis/cloud/aws/amis
#   ami                         = data.aws_ami.ubuntu.id
#   instance_type               = "t3.small"
#   subnet_id                   = aws_subnet.public.id
#   vpc_security_group_ids      = [aws_security_group.ec2.id]
#   key_name                    = "karol"
#   associate_public_ip_address = true

#   user_data_replace_on_change = true
#   user_data                   = <<EOF
# #!/bin/bash
# curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys
# export DEBIAN_FRONTEND=noninteractive
# apt update
# apt install -y python3 python3-pip

# pip3 install --extra-index-url https://dxsxsb220w9y2.cloudfront.net bulletin==0.0.5

# # create systemd unit
# cat <<FILE > /etc/systemd/system/bulletin.service
# [Unit]
# Description=Bulletin
# After=network.target

# [Service]
# Type=simple
# User=ubuntu
# WorkingDirectory=/home/ubuntu
# ExecStart=/usr/bin/python3 -m bulletin p2p --host 0.0.0.0 --port 12345
# Restart=on-failure

# [Install]
# WantedBy=multi-user.target
# FILE

# systemctl daemon-reload
# systemctl enable bulletin.service
# systemctl start bulletin.service
# EOF

#   tags = {
#     Name = "${local.prefix}-p2p"
#   }
# }

# resource "aws_ec2_instance_state" "relay" {
#   instance_id = aws_instance.relay.id
#   state       = "running"
#   # state      = "stopped"
# }

# resource "aws_ec2_instance_state" "p2p" {
#   instance_id = aws_instance.p2p.id
#   state       = "running"
#   # state = "stopped"
# }

# resource "aws_ec2_instance_state" "redis" {
#   instance_id = aws_instance.redis.id
#   state       = "running"
#   # state       = "stopped"
# }

# output "redis_ip" {
#   value = aws_instance.redis.public_ip
# }

# output "relay_ip" {
#   value = aws_instance.relay.public_ip
# }

# output "p2p_ip" {
#   value = aws_instance.p2p.public_ip
# }

output "function_name" {
  value = module.lambda.lambda_function_name
}
