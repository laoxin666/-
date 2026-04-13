# 云端部署：算力与临时文件在容器内，用户通过浏览器上传/下载。
FROM python:3.12-slim

WORKDIR /app

# jpegtran 可选，用于 JPEG 无损优化（无则自动跳过）
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg-turbo-progs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY image_tool.py web_app.py ./
COPY templates ./templates/

ENV IMG_TOOL_CLOUD=1
ENV PORT=8080

EXPOSE 8080

CMD exec gunicorn --bind "0.0.0.0:${PORT}" --workers 2 --threads 4 --timeout 300 web_app:app
