# IAM 委托（Agency）
# 授权 CES 经 SMN 推送告警；权限收敛到 CSS / CES / LTS。
resource "huaweicloud_identity_policy" "alarm" {
  name        = "${var.stack_prefix}-policy"
  description = "Permissions for CSS cluster alarm management workloads (CSS / CES / LTS)"
  policy_document = jsonencode({
    Version = "5.0",
    Statement = [
      {
        Action   = ["css:*:*"],
        Effect   = "Allow",
        Resource = ["*"]
      },
      {
        Action   = ["ces:*:*"],
        Effect   = "Allow",
        Resource = ["*"]
      },
      {
        Action   = ["lts:*:*"],
        Effect   = "Allow",
        Resource = ["*"]
      }
    ]
  })
}

resource "huaweicloud_identity_agency" "alarm" {
  name                  = "${var.stack_prefix}-agency"
  description           = "Agency for CSS cluster alarm management (Cloud Eye / CSS / LTS)"
  delegated_domain_name = "op_svc_ces"

  project_role {
    project = var.region
    roles   = [huaweicloud_identity_policy.alarm.name]
  }
}

output "agency_name" {
  value = huaweicloud_identity_agency.alarm.name
}

terraform {
  required_providers {
    huaweicloud = {
      source = "huaweicloud/huaweicloud"
    }
  }
}
