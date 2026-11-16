# CSS 集群 CES 推荐告警管理

[![License: MIT No Attribution](https://img.shields.io/badge/License-MIT%20No%20Attribution-green.svg)](LICENSE)
[![Huawei Cloud](https://img.shields.io/badge/Huawei%20Cloud-CSS%20%2B%20CES-blue.svg)](https://www.huaweicloud.com/)

## 1. 简介

为 CSS（云搜索服务）集群提供**推荐告警的一键部署与周期巡检**能力：Terraform 拉起集群与配套云资源，Python 工具为指定集群创建推荐 CES 告警规则、周期性检查各集群告警是否匹配基线。适用于需要统一告警基线的 CSS 集群运维场景。

## 2. 目录

- [1. 简介](#1-简介)
- [3. 架构图](#3-架构图)
- [4. 方案亮点](#4-方案亮点)
- [5. 涉及云服务](#5-涉及云服务)
- [6. 前置条件](#6-前置条件)
- [7. 快速开始](#7-快速开始)
- [8. 分步部署](#8-分步部署)
- [9. 使用方法/验证](#9-使用方法验证)
- [10. 清理资源](#10-清理资源)
- [11. 详细说明](#11-详细说明)
- [12. 依赖与致谢](#12-依赖与致谢)
- [13. FAQ/故障排除](#13-faq故障排除)
- [14. 贡献指南](#14-贡献指南)
- [15. 许可证](#15-许可证)
- [16. 联系方式/维护者](#16-联系方式维护者)

## 3. 架构图

```
运维/调度侧（css_create_alarms.py / css_check_alarms.py）
        │  华为云 Python SDK（AK/SK 经环境变量注入）
        ▼
CSS 云搜索 ◄──► CES 云监控（SYS.ES 告警规则） ◄──► SMN 通知
        │                     │
        │                     └── 触发后推送订阅者
        └── IAM 委托（op_svc_ces）授权 + LTS 日志归集
```

## 4. 方案亮点

- **Serverless 运维工具**：创建/巡检脚本可独立运行或作定时任务，不引入常驻计算资源
- **告警基线集中管理**：推荐指标与阈值集中声明，统一调整
- **指标名实测校准**：告警指标采用华为云 `SYS.ES` 集群维度真实指标（`status`/`max_cpu_usage` 等），部署前可按需核对白名单
- **凭据安全**：AK/SK 仅经环境变量注入，不落盘、不入镜像
- **一键拉起**：Terraform 交付 VPC / CSS / CES / LTS / IAM 委托全部配套资源

## 5. 涉及云服务

| 服务 | 用途 |
|------|------|
| CSS（云搜索服务） | 托管 Elasticsearch 集群 |
| CES（云监控） | 集群指标告警规则（命名空间 SYS.ES） |
| SMN（消息通知） | 告警通知推送 |
| LTS（云日志） | 工具运行日志归集 |
| IAM | 委托授权（op_svc_ces） |
| VPC | 私有网络 |

> 资源释放：不再使用时按第 10 章销毁全部资源，避免残留。

## 6. 前置条件

- 华为云账号已实名认证，具备 VPC / CSS / CES / SMN / IAM / LTS 权限
- Terraform ≥ 1.5、Python ≥ 3.8
- 目标区域 CSS 引擎版本为商用可用版本（部署前实查）

## 7. 快速开始

```bash
cd infra
export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"
terraform init
terraform apply
```

## 8. 分步部署

### 步骤 1：拉起基础设施

```bash
cd infra
terraform init
terraform plan
terraform apply
```

预期输出：`Apply complete! Resources: N added`，随后打印 `css_cluster_id`、`css_cluster_name` 等输出。

### 步骤 2：配置告警通知

控制台创建 SMN 主题（如 `sendnotification`）并添加订阅，记录主题 urn：

```
urn:smn:cn-north-4:<project-id>:sendnotification
```

### 步骤 3：为集群创建推荐告警

```bash
cd src
pip install -r requirements.txt
export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"
export HW_PROJECT_ID="<HW_PROJECT_ID>"

python css_create_alarms.py -c <集群名> -e Test \
  -n urn:smn:cn-north-4:<project-id>:sendnotification -r cn-north-4
```

预期输出：逐条「已创建 <告警名>」，末尾「完成：为集群 X 创建 6 条告警」。

## 9. 使用方法/验证

部署完成后，请按以下步骤验证功能可用：

### 验证 1：确认告警已创建

控制台 → 云监控 → 告警规则，确认出现 `Test-CSS-<集群名>-<指标>-Alarm` 的 6 条规则（状态为「正常」）。

### 验证 2：运行巡检脚本

```bash
python css_check_alarms.py -e "" -r cn-north-4
```

预期输出汇总行：`跨 N 个集群 — 匹配 6，缺失 0，不匹配 0`（每集群 6 条推荐告警全匹配）。

### 验证 3：触发通知链路（可选）

在云监控控制台将某条告警阈值临时调低触发，确认订阅邮箱/手机收到 SMN 通知。

> ⚠️ 请在部署完成后按上述步骤自行验证，确认业务功能可用后再投入使用。若验证输出与本文不符，请先排查环境配置（凭据 / 区域 / 集群名）后重试。

## 10. 清理资源

```bash
cd infra
terraform destroy
```

SMN 主题与订阅请在控制台单独删除。释放资源可避免残留。

## 11. 详细说明

### 推荐告警基线

> 指标名取自华为云 `SYS.ES` 集群维度真实指标（实测白名单），维度为 `cluster_id`。

| 指标 | 统计 | 周期(s) | 连续次数 | 算子 | 阈值 |
|------|------|--------|---------|------|------|
| status | 最大 | 300 | 5 | ≥ | 1（黄色：部分副本缺失） |
| status | 最大 | 300 | 5 | ≥ | 2（红色：数据缺失） |
| max_cpu_usage | 最大 | 300 | 5 | ≥ | 80% |
| max_jvm_heap_usage | 最大 | 300 | 5 | ≥ | 85% |
| disk_util | 最大 | 300 | 5 | ≥ | 80% |
| backup_failed_task_count | 最大 | 300 | 5 | ≥ | 1 |

### 工具参数

| 脚本 | 参数 | 说明 |
|------|------|------|
| css_create_alarms.py | `-c` 集群名/ID（必填） | 目标集群 |
| | `-e` 环境名 | 告警名前缀，默认 Test |
| | `-n` SMN urn 列表 | 告警通知目标 |
| | `-f` 最小空闲 MB | 剩余空间阈值兜底 |
| | `-r` 区域 | 默认 cn-north-4 |
| css_check_alarms.py | `-e` 集群名前缀 | 只检查匹配前缀的集群 |
| | `-n` / `-f` / `-r` | 同上 |

## 12. 依赖与致谢

主要依赖：

| 依赖 | 用途 |
|------|------|
| Terraform（≥ 1.5）+ huaweicloud Provider | 基础设施编排 |
| 华为云 Python SDK（huaweicloudsdkcss / huaweicloudsdkces 等） | 告警创建与巡检工具 |
| Python（≥ 3.8） | 工具运行时 |

致谢：感谢开源社区在 Elasticsearch 运维与监控告警领域的最佳实践积累。

## 13. FAQ/故障排除

| 问题 | 处理 |
|------|------|
| `terraform apply` 报 CSS 引擎版本错误 | 目标区域该版本不可用，按区域实查商用版本后改 `css_engine_version` 重试 |
| 创建告警报 `ces.0014` 指标白名单错误 | 用 `ListMetrics` 接口核对 `SYS.ES` / `cluster_id` 维度下可用指标名后调整基线 |
| 巡检输出全部「缺失告警」 | 检查是否已运行创建工具、集群名/ID 是否匹配、区域是否一致 |
| 告警未触发通知 | 确认 SMN 主题已创建并完成订阅；确认 `notification_list` 填入了主题 urn |
| 凭据报错 | 确认已设置 `HW_ACCESS_KEY` / `HW_SECRET_KEY` / `HW_PROJECT_ID` 三个环境变量 |

## 14. 贡献指南

欢迎提交 Issue 与 Pull Request。提交前请确保：

- 代码改动通过 `terraform validate`（infra/）与本地功能自测（src/）
- 文档改动与实际命令行为一致
- 不引入硬编码凭据或敏感信息

## 15. 许可证

本实践采用 [MIT No Attribution](LICENSE) 许可证。

## 16. 联系方式/维护者

- 提交者：Shangdongd
