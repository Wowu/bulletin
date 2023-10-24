variable "prefix" {
  type = string
}

variable "src" {
  type = string
}

variable "environment_variables" {
  type = map(string)
}

variable "file_system_arn" {
  type = string
  default = ""
}

variable "file_system_local_mount_path" {
  type = string
  default = ""
}

variable "vpc_security_group_ids" {
  type = list(string)
  default = []
}

variable "vpc_subnet_ids" {
  type = list(string)
  default = []
}

variable "layers" {
  type = list(string)
  default = []
}
