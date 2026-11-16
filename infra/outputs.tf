output "vpc_id" {
  value = module.vpc.vpc_id
}

output "css_cluster_id" {
  value = module.css.cluster_id
}

output "css_cluster_name" {
  value = module.css.cluster_name
}

output "ces_alarm_ids" {
  value = module.ces.alarm_ids
}

output "agency_name" {
  value = module.iam_agency.agency_name
}

output "lts_group" {
  value = module.lts.group_name
}
