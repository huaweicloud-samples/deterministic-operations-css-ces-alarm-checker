# VPC 网络 —— 为 CSS 集群提供私有网络环境
# 告警工具以本地进程 / 定时任务运行，通过控制面 API 访问 CSS/CES，
# 无需 VPC 内公网出口，故不创建 NAT / EIP。
resource "huaweicloud_vpc" "this" {
  name = "${var.stack_prefix}-vpc"
  cidr = var.vpc_cidr
}

resource "huaweicloud_vpc_subnet" "this" {
  name       = "${var.stack_prefix}-subnet"
  cidr       = var.subnet_cidr
  gateway_ip = cidrhost(var.subnet_cidr, 1)
  vpc_id     = huaweicloud_vpc.this.id
}

resource "huaweicloud_networking_secgroup" "this" {
  name        = "${var.stack_prefix}-sg"
  description = "Security group for the CSS cluster alarm management tool"
}

resource "huaweicloud_networking_secgroup_rule" "egress_https" {
  direction         = "egress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.this.id
  description       = "HTTPS to Huawei Cloud APIs and package mirrors"
}

resource "huaweicloud_networking_secgroup_rule" "egress_css" {
  direction         = "egress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = var.css_port
  port_range_max    = var.css_port
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.this.id
  description       = "CSS cluster REST endpoint access (port 9200)"
}

resource "huaweicloud_networking_secgroup_rule" "ingress_ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.allowed_cidr
  security_group_id = huaweicloud_networking_secgroup.this.id
  description       = "SSH admin access (restrict in production)"
}

output "vpc_id" {
  value = huaweicloud_vpc.this.id
}

output "subnet_id" {
  value = huaweicloud_vpc_subnet.this.id
}

output "security_group_id" {
  value = huaweicloud_networking_secgroup.this.id
}

terraform {
  required_providers {
    huaweicloud = {
      source = "huaweicloud/huaweicloud"
    }
  }
}
