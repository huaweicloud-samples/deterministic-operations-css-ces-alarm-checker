terraform {
  required_version = ">= 1.5"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.70"
    }
  }
}

provider "huaweicloud" {
  region = var.region
  # AK/SK 从环境变量读取，不硬编码
  # export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
  # export HW_SECRET_KEY="<HW_SECRET_KEY>"
}
