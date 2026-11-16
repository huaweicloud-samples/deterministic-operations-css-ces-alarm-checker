variable "stack_prefix" {
  type = string
}

variable "cluster_id" {
  type = string
}

variable "cluster_name" {
  type    = string
  default = ""
}

variable "notification_list" {
  type    = list(string)
  default = []
}

variable "free_storage_threshold" {
  type    = number
  default = 20480
}
