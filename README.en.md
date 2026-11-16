# CSS Cluster CES Recommended Alarm Management

[![License: MIT No Attribution](https://img.shields.io/badge/License-MIT%20No%20Attribution-green.svg)](LICENSE)
[![Huawei Cloud](https://img.shields.io/badge/Huawei%20Cloud-CSS%20%2B%20CES-blue.svg)](https://www.huaweicloud.com/)

## 1. Overview

A **one-click deployment and periodic inspection solution for recommended alarms on CSS (Cloud Search Service) clusters**: Terraform provisions the cluster and supporting cloud resources, and the Python tools create the recommended CES alarm rules for a given cluster and periodically check whether the alarms of each cluster match the baseline. It is intended for O&M scenarios where a unified alarm baseline is required across CSS clusters.

## 2. Table of Contents

- [1. Overview](#1-overview)
- [3. Architecture Diagram](#3-architecture-diagram)
- [4. Highlights](#4-highlights)
- [5. Cloud Services Involved](#5-cloud-services-involved)
- [6. Prerequisites](#6-prerequisites)
- [7. Quick Start](#7-quick-start)
- [8. Step-by-Step Deployment](#8-step-by-step-deployment)
- [9. Usage / Verification](#9-usage--verification)
- [10. Resource Cleanup](#10-resource-cleanup)
- [11. Detailed Description](#11-detailed-description)
- [12. Dependencies and Acknowledgements](#12-dependencies-and-acknowledgements)
- [13. FAQ / Troubleshooting](#13-faq--troubleshooting)
- [14. Contributing](#14-contributing)
- [15. License](#15-license)
- [16. Contact / Maintainers](#16-contact--maintainers)

## 3. Architecture Diagram

```
O&M Side (css_create_alarms.py / css_check_alarms.py)
        |  Huawei Cloud Python SDK (AK/SK injected via environment variables)
        v
CSS Cloud Search <--> CES Cloud Eye (SYS.ES alarm rules) <--> SMN Notification
        |                       |
        |                       +-- Push notifications to subscribers when triggered
        +-- IAM Agency (op_svc_ces) authorization + LTS log aggregation
```

## 4. Highlights

- **Serverless O&M Tools**: The creation / inspection scripts can run standalone or as scheduled tasks, with no always-on compute resources
- **Centralized Alarm Baseline**: Recommended metrics and thresholds are declared centrally for unified tuning
- **Empirically Calibrated Metric Names**: Alarm metrics use the real metrics under the Huawei Cloud `SYS.ES` cluster dimension (`status`, `max_cpu_usage`, etc.); the whitelist can be verified per region before deployment
- **Credential Security**: AK/SK are injected only via environment variables, never written to disk or baked into images
- **One-Click Provisioning**: Terraform delivers VPC / CSS / CES / LTS / IAM Agency and all supporting resources

## 5. Cloud Services Involved

| Service | Purpose |
|---------|---------|
| CSS (Cloud Search Service) | Managed Elasticsearch cluster |
| CES (Cloud Eye) | Cluster metric alarm rules (namespace `SYS.ES`) |
| SMN (Simple Message Notification) | Alarm notification delivery |
| LTS (Log Tank Service) | Tool runtime log aggregation |
| IAM | Agency authorization (`op_svc_ces`) |
| VPC | Private network |

> Resource cleanup: when no longer needed, destroy all resources as described in Chapter 10 to avoid leftovers.

## 6. Prerequisites

- A Huawei Cloud account with real-name verification and permissions for VPC / CSS / CES / SMN / IAM / LTS
- Terraform >= 1.5, Python >= 3.8
- A commercially available CSS engine version in the target region (check availability before deployment)

## 7. Quick Start

```bash
cd infra
export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"
terraform init
terraform apply
```

## 8. Step-by-Step Deployment

### Step 1: Provision the Infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply
```

Expected output: `Apply complete! Resources: N added`, followed by outputs such as `css_cluster_id` and `css_cluster_name`.

### Step 2: Configure Alarm Notifications

Create an SMN topic (e.g., `sendnotification`) in the console and add subscriptions. Record the topic URN:

```
urn:smn:cn-north-4:<project-id>:sendnotification
```

### Step 3: Create Recommended Alarms for the Cluster

```bash
cd src
pip install -r requirements.txt
export HW_ACCESS_KEY="<HW_ACCESS_KEY>"
export HW_SECRET_KEY="<HW_SECRET_KEY>"
export HW_PROJECT_ID="<HW_PROJECT_ID>"

python css_create_alarms.py -c <cluster-name> -e Test \
  -n urn:smn:cn-north-4:<project-id>:sendnotification -r cn-north-4
```

Expected output: `Created <alarm-name>` for each rule, ending with `Done: created 6 alarms for cluster X`.

## 9. Usage / Verification

After deployment, follow the steps below to confirm that the system works:

### Verification 1: Confirm the Alarms Have Been Created

Console -> Cloud Eye -> Alarm Rules. Confirm that the 6 rules named `Test-CSS-<cluster-name>-<metric>-Alarm` appear with the state "Normal".

### Verification 2: Run the Inspection Script

```bash
python css_check_alarms.py -e "" -r cn-north-4
```

Expected summary line: `Across N cluster(s) - matched 6, missing 0, mismatched 0` (all 6 recommended alarms match per cluster).

### Verification 3: Trigger the Notification Chain (Optional)

Temporarily lower the threshold of one alarm in the Cloud Eye console to trigger it, and confirm that the subscribed email / phone receives the SMN notification.

> ⚠️ After deployment, please run the verifications above yourself. Confirm that the business functions work as expected before putting the system into production use. If the actual output does not match this document, please check your environment configuration (credentials / region / cluster name) and retry.

## 10. Resource Cleanup

```bash
cd infra
terraform destroy
```

Delete the SMN topic and subscriptions from the console separately. Releasing them avoids leftover resources.

## 11. Detailed Description

### Recommended Alarm Baseline

> Metric names are taken from the real metrics under the Huawei Cloud `SYS.ES` cluster dimension (verified whitelist), with `cluster_id` as the dimension.

| Metric | Statistic | Period (s) | Consecutive Count | Operator | Threshold |
|--------|-----------|------------|------------|----------|-----------|
| status | Maximum | 300 | 5 | >= | 1 (yellow: some replicas missing) |
| status | Maximum | 300 | 5 | >= | 2 (red: data missing) |
| max_cpu_usage | Maximum | 300 | 5 | >= | 80% |
| max_jvm_heap_usage | Maximum | 300 | 5 | >= | 85% |
| disk_util | Maximum | 300 | 5 | >= | 80% |
| backup_failed_task_count | Maximum | 300 | 5 | >= | 1 |

### Tool Parameters

| Script | Parameter | Description |
|--------|-----------|-------------|
| css_create_alarms.py | `-c` cluster name / ID (required) | Target cluster |
| | `-e` environment name | Alarm name prefix; default `Test` |
| | `-n` SMN URN list | Alarm notification targets |
| | `-f` minimum free MB | Free-space threshold fallback |
| | `-r` region | Default `cn-north-4` |
| css_check_alarms.py | `-e` cluster name prefix | Only inspect clusters matching the prefix |
| | `-n` / `-f` / `-r` | Same as above |

## 12. Dependencies and Acknowledgements

Key dependencies:

| Dependency | Purpose |
|------------|---------|
| Terraform (>= 1.5) + huaweicloud Provider | Infrastructure provisioning |
| Huawei Cloud Python SDK (huaweicloudsdkcss / huaweicloudsdkces, etc.) | Alarm creation and inspection tools |
| Python (>= 3.8) | Tool runtime |

Acknowledgements: thanks to the open-source community for the best practices in Elasticsearch O&M and monitoring/alarm management.

## 13. FAQ / Troubleshooting

| Issue | Resolution |
|-------|------------|
| `terraform apply` reports a CSS engine version error | The version is not available in the target region. After checking the commercial version per region, change `css_engine_version` and retry. |
| Alarm creation fails with `ces.0014` metric whitelist error | Use the `ListMetrics` API to verify the available metric names under `SYS.ES` / `cluster_id`, then adjust the baseline. |
| Inspection output reports "alarm missing" for everything | Confirm that the creation tool has been run, that the cluster name / ID matches, and that the region is consistent. |
| Alarms are not triggering notifications | Confirm that the SMN topic has been created and that subscriptions have been completed; confirm that the topic URN has been added to `notification_list`. |
| Credential errors | Confirm that the three environment variables `HW_ACCESS_KEY` / `HW_SECRET_KEY` / `HW_PROJECT_ID` have been set. |

## 14. Contributing

Issues and Pull Requests are welcome. Before submitting:

- Code changes must pass `terraform validate` (infra/) and local functional self-tests (src/)
- Documentation changes must match the actual command behavior
- Do not introduce hardcoded credentials or sensitive information

## 15. License

This sample is licensed under the [MIT No Attribution](LICENSE) license.

## 16. Contact / Maintainers

- Submitted by: Shangdongd
