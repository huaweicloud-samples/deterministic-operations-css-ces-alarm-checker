variable "region" {
  type    = string
  default = "cn-north-4"
}

variable "stack_prefix" {
  type    = string
  default = "cssalarm"
}

variable "vpc_cidr" {
  type    = string
  default = "192.168.0.0/16"
}

variable "subnet_cidr" {
  type    = string
  default = "192.168.1.0/24"
}

variable "css_port" {
  type    = number
  default = 9200
}

variable "allowed_cidr" {
  type    = string
  default = "192.168.0.0/16"
}

variable "availability_zone" {
  type    = string
  default = "cn-north-4a"
}

variable "css_flavor" {
  type    = string
  default = "ess.spec-4u8g"
}

variable "css_node_count" {
  type    = number
  default = 1
}

variable "css_volume_type" {
  type    = string
  default = "HIGH"
}

variable "css_volume_size" {
  type    = number
  default = 40
}

variable "css_engine_version" {
  type = string
  # 注意：CSS 引擎版本有生命周期限制，部署前请按目标 region 实查商用可用版本
  # （控制台创建页或官方版本生命周期公告），把可用版本写死到此默认值（C9）。
  default = "7.10.2"
}

variable "free_storage_threshold" {
  type    = number
  default = 20480
}

variable "alarm_notification_list" {
  type    = list(string)
  default = []
}
