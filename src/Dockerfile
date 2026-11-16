# CSS 集群 CES 告警工具运行镜像
# 基于华为云 Python SDK 运行时
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY css_create_alarms.py css_check_alarms.py ./

# 凭据经环境变量注入，不落盘
ENV HW_ACCESS_KEY="" HW_SECRET_KEY="" HW_PROJECT_ID="" HW_REGION="cn-north-4"

ENTRYPOINT ["python", "css_check_alarms.py"]
