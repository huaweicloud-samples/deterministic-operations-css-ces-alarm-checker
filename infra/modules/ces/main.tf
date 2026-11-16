# CES（云监控 Cloud Eye）告警规则
# 维度使用 CSS 集群 id，命名空间 SYS.ES（实测：华为云 CSS 集群指标命名空间为 SYS.ES，
# 维度为 cluster_id，非 SYS.CSS / css_cluster_id）。
# 指标名以华为云 SYS.ES 集群维度真实指标为准（ListMetrics 实测白名单校验）：
#   status                集群健康状态（0=可用 / 1=部分副本缺失 / 2=数据缺失）
#   max_cpu_usage         最大 CPU 利用率（%）
#   max_jvm_heap_usage    最大 JVM 堆使用率（%）
#   disk_util             最大磁盘使用率（%）
#   max_load_average      最大节点 Load 值
#   backup_failed_task_count  自动备份失败任务数
locals {
  alarms = {
    "status_yellow" = {
      metric_name = "status"
      filter      = "max"
      operator    = ">="
      value       = 1
    }
    "status_red" = {
      metric_name = "status"
      filter      = "max"
      operator    = ">="
      value       = 2
    }
    "cpu_usage" = {
      metric_name = "max_cpu_usage"
      filter      = "max"
      operator    = ">="
      value       = 80
    }
    "jvm_heap_usage" = {
      metric_name = "max_jvm_heap_usage"
      filter      = "max"
      operator    = ">="
      value       = 85
    }
    "disk_util" = {
      metric_name = "disk_util"
      filter      = "max"
      operator    = ">="
      value       = 80
    }
    "backup_failed" = {
      metric_name = "backup_failed_task_count"
      filter      = "max"
      operator    = ">="
      value       = 1
    }
  }
}

resource "huaweicloud_ces_alarmrule" "this" {
  for_each = local.alarms

  alarm_name = "${var.stack_prefix}-${each.key}"

  metric {
    namespace = "SYS.ES"
    dimensions {
      name  = "cluster_id"
      value = var.cluster_id
    }
  }

  condition {
    metric_name         = each.value.metric_name
    period              = 300
    filter              = each.value.filter
    comparison_operator = each.value.operator
    value               = each.value.value
    count               = 5
    unit                = "counts"
  }

  alarm_actions {
    type              = "notification"
    notification_list = var.notification_list
  }

  alarm_action_enabled = true
}

output "alarm_ids" {
  value = { for k, v in huaweicloud_ces_alarmrule.this : k => v.id }
}

terraform {
  required_providers {
    huaweicloud = {
      source = "huaweicloud/huaweicloud"
    }
  }
}
