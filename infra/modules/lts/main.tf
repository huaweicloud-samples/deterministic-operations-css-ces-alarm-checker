# LTS（云日志服务）日志组 —— 归集告警工具运行日志
resource "huaweicloud_lts_group" "this" {
  group_name  = "${var.stack_prefix}-logs"
  ttl_in_days = 7
}

output "group_name" {
  value = huaweicloud_lts_group.this.group_name
}

terraform {
  required_providers {
    huaweicloud = {
      source = "huaweicloud/huaweicloud"
    }
  }
}
