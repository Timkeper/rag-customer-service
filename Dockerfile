# 智答 v2 · 腾讯云 CloudBase 云托管镜像
FROM python:3.11-slim

WORKDIR /app/src

# 先装依赖（利用层缓存）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝源码与知识库（保持相对路径结构：src/../06-knowledge-base）
COPY src/ /app/src/
COPY 06-knowledge-base/ /app/06-knowledge-base/

# 数据目录（SQLite + Chroma 首次启动时自动初始化）
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "server.py"]
