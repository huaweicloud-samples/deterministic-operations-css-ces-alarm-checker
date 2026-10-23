# css-ces-alarm-checker — 华为云基础设施
# 通过 Terraform 一键拉起 CSS 集群告警巡检所需的云资源：
#   CSS（云搜索服务）          —— 托管 Elasticsearch 集群
#   CES（云监控 Cloud Eye）    —— 集群推荐告警规则
#   IAM 委托（Agency）         —— 授权 CES 经 SMN 推送告警
#   LTS（云日志服务）          —— 工具运行日志归集
#   VPC                        —— 集群与工具的私有网络环境（控制面 API 访问，无需公网出口）

module "vpc" {
  source       = "./modules/vpc"
  stack_prefix = var.stack_prefix
  vpc_cidr     = var.vpc_cidr
  subnet_cidr  = var.subnet_cidr
  css_port     = var.css_port
  allowed_cidr = var.allowed_cidr
}

module "lts" {
  source       = "./modules/lts"
  stack_prefix = var.stack_prefix
}

module "css" {
  source            = "./modules/css"
  stack_prefix      = var.stack_prefix
  region            = var.region
  vpc_id            = module.vpc.vpc_id
  subnet_id         = module.vpc.subnet_id
  security_group_id = module.vpc.security_group_id
  availability_zone = var.availability_zone
  flavor            = var.css_flavor
  node_count        = var.css_node_count
  volume_type       = var.css_volume_type
  volume_size       = var.css_volume_size
  engine_version    = var.css_engine_version
}

module "ces" {
  source                 = "./modules/ces"
  stack_prefix           = var.stack_prefix
  cluster_id             = module.css.cluster_id
  cluster_name           = module.css.cluster_name
  notification_list      = var.alarm_notification_list
  free_storage_threshold = var.free_storage_threshold
}

module "iam_agency" {
  source       = "./modules/iam_agency"
  stack_prefix = var.stack_prefix
  region       = var.region
}
