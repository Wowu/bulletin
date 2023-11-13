resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

locals {
  prefix = "benchmark-redis-${random_string.random.result}"
}

#
# Lambda
#

module "lambda" {
  source = "../base"

  src    = "${path.module}/source"
  prefix = local.prefix

  environment_variables = {
    SERVER_IP = aws_eip.main.public_ip
  }
}

#
# Additional resources
#

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

data "aws_region" "current" {}

# default VPC
data "aws_vpc" "default" {
  default = true
}

data "aws_subnet" "a" {
  filter {
    name   = "availability-zone"
    values = ["${data.aws_region.current.name}a"]
  }

  vpc_id = data.aws_vpc.default.id
}

# security group for ec2
resource "aws_security_group" "ec2" {
  name        = local.prefix
  description = local.prefix

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

resource "aws_instance" "main" {
  # Redis AMI
  # https://bitnami.com/stack/redis/cloud/aws/amis
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  subnet_id              = data.aws_subnet.a.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  key_name               = "karol"

  user_data_replace_on_change = true
  user_data                   = <<EOF
#!/bin/bash
curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys
export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y redis-server
sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
systemctl restart redis-server

EOF

  tags = {
    Name = local.prefix
  }
}

resource "aws_ec2_instance_state" "main" {
  instance_id = aws_instance.main.id
  state       = var.instance_state
}

resource "aws_eip" "main" {
  instance = aws_instance.main.id
}

output "ip" {
  value = aws_eip.main.public_ip
}
