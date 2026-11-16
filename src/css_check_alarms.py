#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSS 集群 CES 告警检查工具
========================
检查每个 CSS（云搜索服务）集群是否配置了推荐的 CES（云监控 Cloud Eye）告警规则。
可独立运行，或作为定时任务周期性巡检。

依赖服务：
  CSS（云搜索服务，huaweicloud_css_cluster）—— 托管 Elasticsearch 集群
  CES（云监控 Cloud Eye，huaweicloud_ces_alarmrule）—— 指标告警规则

用法：
  python css_check_alarms.py [-e CSS前缀] [-n SMN_urn] [-f 空闲MB] [-r 区域]
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
from huaweicloudsdkcss.v1.region.css_region import CssRegion
from huaweicloudsdkcss.v1 import CssClient
from huaweicloudsdkces.v2.region.ces_region import CesRegion
from huaweicloudsdkces.v2 import CesClient

DEFAULT_REGION = "cn-north-4"
DEFAULT_SMN_TOPIC = "sendnotification"
CSS_NAMESPACE = "SYS.ES"
CSS_DIMENSION = "cluster_id"

MIN_CSS_FREESPACE = 2048.0
MIN_CSS_FREESPACE_PERCENT = 0.20
DEFAULT_CSS_FREESPACE = MIN_CSS_FREESPACE

# CES 统计量与比较算子的取值约定（filter / comparison_operator 字段）
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


def list_clusters(css_client, prefix):
    from huaweicloudsdkcss.v1 import ListClustersDetailsRequest
    resp = css_client.list_clusters_details(ListClustersDetailsRequest())
    clusters = getattr(resp, "clusters", None) or []
    out = []
    for c in clusters:
        name = getattr(c, "name", None)
        if name and name.startswith(prefix):
            out.append((getattr(c, "id", None), name))
    return out


def get_cluster_detail(css_client, cluster_id):
    try:
        from huaweicloudsdkcss.v1 import ShowClusterDetailRequest
        resp = css_client.show_cluster_detail(ShowClusterDetailRequest(cluster_id=cluster_id))
        return getattr(resp, "cluster", None)
    except Exception as e:  # noqa
        logging.warning("获取集群详情失败: %s", e)
        return None


def calc_storage(detail, wanted_free):
    """依据集群存储配置估算剩余空间告警阈值（MB，保留兼容）。"""
    esfree = float(wanted_free)
    if detail is None:
        return esfree
    node_config = getattr(detail, "ess_node_config", None) or getattr(detail, "instance", None)
    if node_config is not None:
        vol = getattr(node_config, "instance_volume", None) or getattr(node_config, "volume", None)
        if vol is not None:
            size_gb = getattr(vol, "size", None) or getattr(vol, "volume_size", None)
            count = getattr(node_config, "node_count", 1) or 1
            if size_gb:
                return float(int(count) * int(size_gb) * 1024 * MIN_CSS_FREESPACE_PERCENT)
    return esfree


def expected_alarms(cluster_name, detail, desired_free, alarm_action):
    """CSS 集群推荐的 CES 告警指标集合。"""
    return [
        Alarm("status", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 1.0, alarm_action),
        Alarm("status", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 2.0, alarm_action),
        Alarm("max_cpu_usage", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 80.0, alarm_action),
        Alarm("max_jvm_heap_usage", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 85.0, alarm_action),
        Alarm("disk_util", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 80.0, alarm_action),
        Alarm("backup_failed_task_count", "Maximum", 300, 5, "GreaterThanOrEqualToThreshold", 1.0, alarm_action),
    ]


def list_alarms_for_metric(ces_client, cluster_id, metric):
    from huaweicloudsdkces.v2 import ListAlarmRulesRequest
    req = ListAlarmRulesRequest(namespace=CSS_NAMESPACE, limit=100)
    resp = ces_client.list_alarm_rules(req)
    d = resp.to_dict() if hasattr(resp, "to_dict") else {}
    alarms = d.get("alarms", []) or []
    out = []
    for a in alarms:
        policies = a.get("policies", []) or []
        resources = a.get("resources", []) or []
        if not any(p.get("metric_name") == metric for p in policies):
            continue
        dims = []
        for r in resources:
            for dim in (r.get("dimensions", []) or []):
                # v2 响应中维度 value 可能为 null（实测），命名空间+指标名已可定位，维度名匹配即可
                if dim.get("name") == CSS_DIMENSION:
                    dims.append(dim)
        if dims:
            out.append(a)
    return out


class AlarmChecker(object):
    """检查 CES 告警字段是否匹配期望值。"""

    def __init__(self, domain, alarm):
        self.alarm = alarm
        self.domain = domain

    def _check(self, field_name, expected, actual):
        ok = expected == actual
        if not ok:
            logging.warning(
                "%s Alarm: %s 不匹配 (期望 %s, 实际 %s)", self.domain, field_name, expected, actual
            )
        return ok

    def check(self, existing):
        # CES v2 响应结构：policies[]（含 metric_name/filter/period/count/comparison_operator/value）
        # 同指标可能存在多条告警（如 status 的 yellow/red 两档），逐一比对，任一完全匹配即通过
        if isinstance(existing, dict):
            candidates = [existing]
        else:
            candidates = existing or []
        for one in candidates:
            policies = one.get("policies", []) if isinstance(one, dict) else []
            pol = policies[0] if policies else {}
            ok = True
            ok = self._check("metric_name", self.alarm.metric, pol.get("metric_name")) and ok
            ok = self._check("statistic(filter)", STAT_FILTER.get(self.alarm.stat), pol.get("filter")) and ok
            ok = self._check("period", self.alarm.period, pol.get("period")) and ok
            ok = self._check("eval_period(count)", self.alarm.eval_period, pol.get("count")) and ok
            ok = self._check("operator", OPERATOR_MAP.get(self.alarm.operator), pol.get("comparison_operator")) and ok
            ok = self._check("threshold(value)", self.alarm.threshold, pol.get("value")) and ok
            if ok:
                return True
        return False


def process_alarms(css_client, ces_client, prefix, desired_free, alarm_actions):
    our_domains = list_clusters(css_client, prefix)
    logging.info("匹配前缀(%s)的 CSS 集群: %s", prefix, [n for _, n in our_domains])

    missing = ok = not_ok = 0
    for cluster_id, cluster_name in our_domains:
        detail = get_cluster_detail(css_client, cluster_id)
        logging.info("检查集群 %s (id=%s)", cluster_name, cluster_id)
        es_alarms = expected_alarms(cluster_name, detail, desired_free, alarm_actions)
        for es_alarm in es_alarms:
            existing = list_alarms_for_metric(ces_client, cluster_id, es_alarm.metric)
            if not existing:
                logging.warning("%s 缺失告警: %s", cluster_name, es_alarm.metric)
                missing += 1
                continue
            checker = AlarmChecker(cluster_name, es_alarm)
            if checker.check(existing):
                logging.info("%s 告警定义匹配: %s", cluster_name, es_alarm.metric)
                ok += 1
            else:
                not_ok += 1

    logging.info("处理完成；跨 %d 个集群 — 匹配 %d，缺失 %d，不匹配 %d",
                 len(our_domains), ok, missing, not_ok)
    return missing, ok, not_ok


def get_args():
    parser = argparse.ArgumentParser(
        description="检查 CSS 集群是否设置了推荐的 CES 告警。"
    )
    parser.add_argument("-e", "--cssprefix", required=False, default="",
                        help="只检查名称以此前缀开头的 CSS 集群")
    parser.add_argument("-n", "--notify", nargs="+", required=False, default=[],
                        help="告警通知 SMN topic urn 列表")
    parser.add_argument("-f", "--free", required=False, type=float, default=DEFAULT_CSS_FREESPACE,
                        help="最小空闲空间（MB）")
    parser.add_argument("-r", "--region", required=False, default=DEFAULT_REGION,
                        help="华为云区域")
    return parser.parse_args()


def main():
    logger = init_logging()
    os.environ.setdefault("log_level", "INFO")
    logger = setup_local_logging(logger, os.environ["log_level"])

    args = get_args()
    creds, project_id, region = build_credentials(args.region)
    css_client, ces_client = build_clients(creds, region)

    if args.free < MIN_CSS_FREESPACE:
        args.free = MIN_CSS_FREESPACE

    alarm_actions = args.notify or get_default_alarm_actions(region, project_id, DEFAULT_SMN_TOPIC)
    process_alarms(css_client, ces_client, args.cssprefix, args.free, alarm_actions)


if __name__ == "__main__":
    main()
