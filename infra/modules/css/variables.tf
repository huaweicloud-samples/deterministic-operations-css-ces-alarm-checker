variable "stack_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "availability_zone" {
  type = string
}

variable "flavor" {
  type = string
}

variable "node_count" {
  type = number
}

variable "volume_type" {
  type = string
}

variable "volume_size" {
  type = number
}

variable "engine_version" {
  type = string
}
