resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

locals {
  prefix = "benchmark-relay-${random_string.random.result}"
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

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "main" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.small"
  subnet_id     = data.aws_subnet.a.id
  vpc_security_group_ids = [aws_security_group.ec2.id]

  user_data_replace_on_change = true
  user_data = <<EOF
#!/bin/bash
curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys
export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y python3 python3-pip

pip3 install --extra-index-url https://dxsxsb220w9y2.cloudfront.net bulletin==0.0.5

# create systemd unit
cat <<FILE > /etc/systemd/system/bulletin.service
[Unit]
Description=Bulletin
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/python3 -m bulletin relay --host 0.0.0.0 --port 12345
Restart=on-failure

[Install]
WantedBy=multi-user.target
FILE

systemctl daemon-reload
systemctl enable bulletin.service
systemctl start bulletin.service

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
