# 部署指导书

## 1. 前置条件

| 项 | 要求 |
|----|------|
| 华为云账号 | 已实名认证，具备 VPC / CSS / CES / SMN / IAM / LTS 权限 |
| 凭据 | AK/SK（建议使用子账号最小权限），经环境变量注入，不写盘 |
| 工具 | Terraform ≥ 1.5、Python ≥ 3.8 |
| 区域 | 默认 `cn-north-4`，可改 `infra/variables.tf` 的 `region` |

## 2. 一键部署

```bash
# 进入基础设施目录
cd infra

# 配置凭据（环境变量注入，不写盘）
export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"

# 初始化并应用
terraform init
terraform plan
terraform apply
```

> `terraform apply` 前请核对 `variables.tf` 中的资源规格与数量；CSS 引擎版本请按目标区域商用可用版本填写（`css_engine_version`）。

## 3. 部署后必做

### 3.1 创建告警通知主题（SMN）

本实践不自动创建 SMN 主题，由运维按需创建并订阅接收人：

```bash
# 控制台：消息通知服务 → 主题 → 创建主题（如 sendnotification）→ 添加订阅
# 记录主题 urn，形如：
#   urn:smn:cn-north-4:<project-id>:sendnotification
```

### 3.2 为集群创建推荐告警

```bash
cd src
pip install -r requirements.txt

export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"
export HW_PROJECT_ID="<HW_PROJECT_ID>"

python css_create_alarms.py \
  -c <CSS集群名称或ID> \
  -e Test \
  -n urn:smn:cn-north-4:<project-id>:sendnotification \
  -r cn-north-4
```

预期输出：逐条打印「已创建 <告警名>」，末尾「完成：为集群 X 创建 6 条告警」。

### 3.3 周期巡检

```bash
# 检查所有集群（可按前缀过滤）
python css_check_alarms.py -e "" -r cn-north-4

# 输出汇总：匹配 N / 缺失 N / 不匹配 N
```

可配置为定时任务（cron / 云上定时调度）周期性执行。

## 4. 释放资源

```bash
cd infra
terraform destroy
```

> `terraform destroy` 会释放本实践创建的全部云资源；手工创建的 SMN 主题与订阅需在控制台单独删除。释放资源可避免残留。

## 5. 已知约束

| 项 | 说明 |
|----|------|
| CSS 引擎版本 | 有生命周期限制，部署前按目标区域实查商用可用版本并写入 `css_engine_version` |
| 告警指标白名单 | 指标名以华为云 `SYS.ES` 集群维度真实指标为准（`status`/`max_cpu_usage`/`max_jvm_heap_usage`/`disk_util`/`backup_failed_task_count`），部署前可用 `ListMetrics` 核对 |
| SMN 主题 | 需预先创建并完成订阅，否则告警通知不生效 |
| 告警名称前缀 | 使用 `-e` 参数区分环境（Test/Prod），同名告警会重复创建 |
