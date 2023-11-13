terraform {
  backend "s3" {
    bucket         = "328421278917-terraform-states"
    key            = "benchmark.tfstate"
    region         = "us-east-1"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"

  # Make it faster
  skip_region_validation      = true
  skip_credentials_validation = true
  skip_requesting_account_id  = true
}

module "dynamodb" {
  source  = "./modules/dynamodb"
}

output "benchmark_dynamodb" {
  value = module.dynamodb.function_name
}

module "efs" {
  source  = "./modules/efs"
}

output "benchmark_efs" {
  value = module.efs.function_name
}

module "s3" {
  source  = "./modules/s3"
}

output "benchmark_s3" {
  value = module.s3.function_name
}

# module "relay" {
#   source  = "./modules/relay"

#   instance_state = "running"
#   # instance_state = "stopped"
# }

# output "benchmark_relay" {
#   value = module.relay.function_name
# }

# output "relay_ip" {
#   value = module.relay.ip
# }

# module "redis" {
#   source  = "./modules/redis"

#   instance_state = "running"
#   # instance_state = "stopped"
# }

# output "benchmark_redis" {
#   value = module.redis.function_name
# }

# output "redis_ip" {
#   value = module.redis.ip
# }

# module "p2p" {
#   source  = "./modules/p2p"

#   instance_state = "running"
#   # instance_state = "stopped"
# }

# output "benchmark_p2p" {
#   value = module.p2p.function_name
# }

# output "p2p_ip" {
#   value = module.p2p.ip
# }
