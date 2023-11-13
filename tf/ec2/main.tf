terraform {
  backend "s3" {
    bucket  = "328421278917-terraform-states"
    key     = "ec2.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

data "aws_caller_identity" "current" {}

resource "aws_security_group" "main" {
  name = "security group for testing server"

  ingress {
    description = "SSH from the internet"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Mosh from the internet"
    from_port   = 60000
    to_port     = 61000
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# resource "aws_iam_role" "main" {
#   name = "magisterka-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Sid    = ""
#         Principal = {
#           Service = "ec2.amazonaws.com"
#         }
#       },
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Sid    = ""
#         Principal = {
#           Service = "lambda.amazonaws.com"
#         }
#       }
#     ]
#   })

#   inline_policy {
#     name   = "magisterka-policy"
#     policy = <<-EOF
#       {
#         "Version": "2012-10-17",
#         "Statement": [
#           {
#             "Effect": "Allow",
#             "Resource": "*",
#             "Action": [
#               "s3:*",
#               "iam:*",
#               "dynamodb:*",
#               "elasticfilesystem:*",
#               "ec2:*",
#               "ecr:*",
#               "cloudwatch:*",
#               "logs:*",
#               "cloudfront:*",
#               "lambda:*"
#             ]
#           }
#         ]
#       }
#     EOF
#   }

#   tags = {
#     Name = "magisterka-role"
#   }
# }

# resource "aws_iam_instance_profile" "main" {
#   name = "magisterka-instance-profile"
#   role = aws_iam_role.main.name
# }

resource "aws_instance" "main" {
  # https://cloud-images.ubuntu.com/locator/ec2/
  # Ubuntu 22.04, us-east-1
  ami                         = "ami-007855ac798b5175e"
  instance_type               = "t3.small"
  vpc_security_group_ids      = [aws_security_group.main.id]
  associate_public_ip_address = true
  key_name                    = "karol"
  # iam_instance_profile        = aws_iam_instance_profile.main.name
  iam_instance_profile        = "LabInstanceProfile"
  availability_zone           = "us-east-1a"

  user_data = <<-EOF
    #!/bin/bash
    curl https://github.com/wowu.keys >> /home/ubuntu/.ssh/authorized_keys

    export DEBIAN_FRONTEND=noninteractive
    apt update
    apt install -y mosh

    # install docker
    curl https://get.docker.com | bash

    usermod -aG docker ubuntu

    # install nix
    # sh <(curl -L https://nixos.org/nix/install) --daemon

  EOF

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "magisterka-server"
  }
}

resource "aws_eip" "main" {
  instance = aws_instance.main.id
}

output "instance_ip" {
  value = aws_eip.main.public_ip
}

output "instance_id" {
  value = aws_instance.main.id
}
