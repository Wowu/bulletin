resource "random_string" "random" {
  length  = 8
  special = false
  upper = false
}

locals {
  prefix = "benchmark-s3-${random_string.random.result}"
}

#
# Lambda
#

module "lambda" {
  source  = "../base"

  src = "${path.module}/source"
  prefix = local.prefix

  environment_variables = {
    TABLE_NAME = aws_dynamodb_table.table.name
  }
}

#
# Additional resources
#

resource "aws_dynamodb_table" "table" {
  name         = local.prefix
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}
