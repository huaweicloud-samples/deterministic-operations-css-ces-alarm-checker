#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSS 集群 CES 告警创建工具
========================
为指定 CSS（云搜索服务）集群创建推荐的 CES（云监控 Cloud Eye）告警规则，
并授权 CES 通过 SMN（消息通知服务）将告警推送给运维人员。

依赖服务：
  CSS（云搜索服务，huaweicloud_css_cluster）—— 托管 Elasticsearch 集群
  CES（云监控 Cloud Eye，huaweicloud_ces_alarmrule）—— 指标告警规则
  SMN（消息通知服务）—— 告警通知目标
  IAM 委托（Agency，delegated_domain_name=op_svc_ces）—— 运行授权

用法示例：
  python css_create_alarms.py -c <CSS集群名或ID> -e Test \
      -n urn:smn:cn-north-4:<project>:sendnotification -f 20480 -r cn-north-4
凭据（环境变量）：HW_ACCESS_KEY / HW_SECRET_KEY / HW_PROJECT_ID / HW_REGION
"""
import os
import sys
import json
import time
import logging
import argparse
import collections

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcss.v1.region.css_region import CssRegion
from huaweicloudsdkcss.v1 import CssClient
from huaweicloudsdkces.v2.region.ces_region import CesRegion
from huaweicloudsdkces.v2 import CesClient
from huaweicloudsdkces.v2 import (
    CreateAlarmRulesRequest,
)

DEFAULT_REGION = "cn-north-4"
DEFAULT_SMN_TOPIC = "sendnotification"
CSS_NAMESPACE = "SYS.ES"
CSS_DIMENSION = "cluster_id"

# 最小空闲空间（MB），用于剩余空间告警阈值兜底
MIN_CSS_FREESPACE = 2048.0
MIN_CSS_FREESPACE_PERCENT = 0.20
DEFAULT_CSS_FREESPACE = MIN_CSS_FREESPACE

# 华为云 CES 统计量与比较算子的取值约定
STAT_FILTER = {
    "Maximum": "max",
    "Average": "average",
    "Minimum": "min",
    "Sum": "sum",
}
OPERATOR_MAP = {
    "GreaterThanOrEqualToThreshold": ">=",
    "GreaterThanThreshold": ">",
    "LessThanOrEqualToThreshold": "<=",
    "LessThanThreshold": "<",
}

Alarm = collections.namedtuple(
    "Alarm",
    ["metric", "stat", "period", "eval_period", "operator", "threshold", "alarm_action"],
)

LOG_LEVELS = {"CRITICAL": 50, "ERROR": 40, "WARNING": 30, "INFO": 20, "DEBUG": 10}


def init_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    return logger


def setup_local_logging(logger, log_level="INFO"):
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(LOG_LEVELS.get(log_level, LOG_LEVELS["INFO"]))
    return logger


def get_default_alarm_actions(region, project, topic):
    # 未显式指定通知目标时，兜底使用 SMN topic urn
    return [f"urn:smn:{region}:{project}:{topic}"]


def build_credentials(region):
    ak = os.environ.get("HW_ACCESS_KEY", "")
    sk = os.environ.get("HW_SECRET_KEY", "")
    project_id = os.environ.get("HW_PROJECT_ID", "")
    if not ak or not sk or not project_id:
        raise SystemExit(
            "ERROR: 缺少华为云凭据，请设置 HW_ACCESS_KEY / HW_SECRET_KEY / HW_PROJECT_ID"
        )
    return BasicCredentials(ak, sk, project_id), project_id, region


def build_clients(creds, region):
    css_client = (
        CssClient.new_builder()
        .with_credentials(creds)
        .with_region(CssRegion.value_of(region))
        .build()
    )
    ces_client = (
        CesClient.new_builder()
        .with_credentials(creds)
        .with_region(CesRegion.value_of(region))
        .build()
    )
    return css_client, ces_client


def resolve_cluster_id(css_client, cluster_ref):
    """按名称或 id 解析 CSS 集群 id。"""
    request = __import__(
        "huaweicloudsdkcss.v1", fromlist=["ListClustersDetailsRequest"]
    ).ListClustersDetailsRequest()
    resp = css_client.list_clusters_details(request)
    clusters = getattr(resp, "clusters", None) or []
    for c in clusters:
        cid = getattr(c, "id", None)
        cname = getattr(c, "name", None)
        if cluster_ref in (cid, cname):
            return cid, cname
    raise SystemExit(f"ERROR: 未找到 CSS 集群: {cluster_ref}")


def calc_storage(cluster_detail, wanted_free):
    """依据集群存储配置估算剩余空间告警阈值（MB，保留兼容）。"""
    esfree = float(wanted_free)
    if cluster_detail is None:
        logging.warning("无集群详情，使用默认最小空闲空间: %s MB", esfree)
        return esfree
    # CSS 集群详情中存储信息可能位于 instance（节点配置），这里做兼容取值
    node_config = getattr(cluster_detail, "ess_node_config", None) or getattr(
        cluster_detail, "instance", None
    )
    if node_config is not None:
        vol = getattr(node_config, "instance_volume", None) or getattr(
            node_config, "volume", None
        )
        if vol is not None:
            size_gb = getattr(vol, "size", None) or getattr(vol, "volume_size", None)
            count = getattr(node_config, "node_count", 1) or 1
            if size_gb:
                total = int(count) * int(size_gb) * 1024
                esfree = float(int(total * MIN_CSS_FREESPACE_PERCENT))
                logging.info("估算空闲空间阈值(GB->MB): %s", esfree)
                return esfree
    logging.warning("无法解析集群存储，使用默认最小空闲空间: %s MB", esfree)
    return esfree


def get_cluster_detail(css_client, cluster_id):
    try:
        from huaweicloudsdkcss.v1 import ShowClusterDetailRequest
        req = ShowClusterDetailRequest(cluster_id=cluster_id)
        resp = css_client.show_cluster_detail(req)
        return getattr(resp, "cluster", None)
    except Exception as e:  # noqa
        logging.warning("获取集群详情失败: %s", e)
        return None


def build_alarm_list(cluster_name, detail, desired_free, alarm_action):
    """CSS 集群推荐的 CES 告警指标集合（SYS.ES 真实指标）。"""
    es_alarms = [
        Alarm("status", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 1.0, alarm_action),
        Alarm("status", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 2.0, alarm_action),
        Alarm("max_cpu_usage", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 80.0, alarm_action),
        Alarm("max_jvm_heap_usage", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 85.0, alarm_action),
        Alarm("disk_util", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 80.0, alarm_action),
        Alarm("backup_failed_task_count", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 1.0, alarm_action),
    ]
    return es_alarms


def create_one_alarm(ces_client, env, cluster_id, cluster_name, es_alarm):
    alarm_name = "-".join([env, "CSS", cluster_name, es_alarm.metric, "Alarm"])
    # CES v2 创建告警：请求体用原始 dict（绕过强类型模型，docs 实测方式）
    body = {
        "name": alarm_name,
        "description": alarm_name,
        "namespace": CSS_NAMESPACE,
        "type": "MULTI_INSTANCE",
        "policies": [{
            "metric_name": es_alarm.metric,
            "period": es_alarm.period,
            "filter": STAT_FILTER.get(es_alarm.stat, "average"),
            "comparison_operator": OPERATOR_MAP.get(es_alarm.operator, ">="),
            "value": es_alarm.threshold,
            "count": es_alarm.eval_period,
            "unit": "counts",
            "namespace": CSS_NAMESPACE,
            "dimension_name": CSS_DIMENSION,
        }],
        "resources": [[{"name": CSS_DIMENSION, "value": cluster_id}]],
        "alarm_notifications": [{
            "type": "notification",
            "notification_list": list(es_alarm.alarm_action),
        }],
        "enabled": True,
        "notification_enabled": True,
    }
    req = CreateAlarmRulesRequest(body=body)
    ces_client.create_alarm_rules(req)
    return alarm_name


def get_args():
    parser = argparse.ArgumentParser(
        description="为给定 CSS 集群创建推荐的 CES 告警规则。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--cluster", required=True,
                        help="CSS 集群名称或 id")
    parser.add_argument("-e", "--env", required=False, default="Test",
                        help="环境名（Test/Prod），作为告警名前缀")
    parser.add_argument("-n", "--notify", nargs="+", required=False, default=[],
                        help="告警通知 SMN topic urn 列表")
    parser.add_argument("-f", "--free", required=False, type=float, default=DEFAULT_CSS_FREESPACE,
                        help="最小空闲空间（MB），用于剩余空间告警")
    parser.add_argument("-r", "--region", required=False, default=DEFAULT_REGION,
                        help="华为云区域")
    args = parser.parse_args()

    if args.free < MIN_CSS_FREESPACE:
        logging.info("空闲空间 %s 小于 CSS 最小 %s，已重置", args.free, MIN_CSS_FREESPACE)
        args.free = MIN_CSS_FREESPACE
    return args


def main():
    logger = init_logging()
    os.environ.setdefault("log_level", "INFO")
    logger = setup_local_logging(logger, os.environ["log_level"])

    args = get_args()
    creds, project_id, region = build_credentials(args.region)
    css_client, ces_client = build_clients(creds, region)

    cluster_id, cluster_name = resolve_cluster_id(css_client, args.cluster)
    detail = get_cluster_detail(css_client, cluster_id)

    alarm_actions = args.notify or get_default_alarm_actions(region, project_id, DEFAULT_SMN_TOPIC)

    es_alarms = build_alarm_list(cluster_name, detail, args.free, alarm_actions)
    logging.info("将为集群 %s 创建 %d 条告警", cluster_name, len(es_alarms))

    created = 0
    for es_alarm in es_alarms:
        name = create_one_alarm(ces_client, args.env, cluster_id, cluster_name, es_alarm)
        logging.info("已创建 %s", name)
        created += 1

    logging.info("完成：为集群 %s 创建 %d 条告警", cluster_name, created)


if __name__ == "__main__":
    main()
