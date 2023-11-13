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
    BUCKET_NAME = aws_s3_bucket.bucket.id
  }
}

#
# Additional resources
#

resource "aws_s3_bucket" "bucket" {
  bucket = local.prefix
  force_destroy = true
}

