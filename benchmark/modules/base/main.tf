data "aws_caller_identity" "current" {}

#
# Lambda
#

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 4.7"

  function_name                  = var.prefix
  handler                        = "main.lambda_handler"
  runtime                        = "python3.9"
  publish                        = true
  timeout                        = 15
  memory_size                    = 2048
  ephemeral_storage_size         = 10240
  reserved_concurrent_executions = 2

  create_package  = true
  build_in_docker = true
  source_path     = var.src

  layers = var.layers

  # AWS Academy
  create_role = false
  # lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/magisterka-role"
  lambda_role = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  environment_variables = var.environment_variables

  vpc_security_group_ids = var.vpc_security_group_ids == [] ? null : var.vpc_security_group_ids
  vpc_subnet_ids         = var.vpc_subnet_ids == [] ? null : var.vpc_subnet_ids

  file_system_arn              = var.file_system_arn == "" ? null : var.file_system_arn
  file_system_local_mount_path = var.file_system_local_mount_path == "" ? null : var.file_system_local_mount_path

  # Force redeploy
  hash_extra = "1"
}
