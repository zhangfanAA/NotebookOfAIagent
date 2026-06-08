# ============================================
# 智能学习助手 — Dockerfile (API 后端)
# ============================================
# 构建: docker build -t learning-assistant-api .
# ============================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 系统依赖（gcc 用于编译 C 扩展）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data/pdfs data/chroma_db logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# 默认启动 API 后端
CMD ["python", "main.py", "api", "--port", "8000", "--skip-check"]
