# CSS（云搜索服务）集群 —— 托管 Elasticsearch 集群
resource "huaweicloud_css_cluster" "this" {
  name              = "${var.stack_prefix}-css"
  engine_version    = var.engine_version
  security_mode     = false
  https_enabled     = false
  availability_zone = var.availability_zone

  ess_node_config {
    flavor          = var.flavor
    instance_number = var.node_count

    volume {
      volume_type = var.volume_type
      size        = var.volume_size
    }
  }

  vpc_id            = var.vpc_id
  subnet_id         = var.subnet_id
  security_group_id = var.security_group_id
}

output "cluster_id" {
  value = huaweicloud_css_cluster.this.id
}

output "cluster_name" {
  value = huaweicloud_css_cluster.this.name
}

terraform {
  required_providers {
    huaweicloud = {
      source = "huaweicloud/huaweicloud"
    }
  }
}
