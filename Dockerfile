# ============================================
# 智能学习助手 — Dockerfile
# ============================================
# 构建: docker build -t learning-assistant .
# 运行: docker run -p 8501:8501 -p 8000:8000 learning-assistant
# ============================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
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
EXPOSE 8501 8000

# 默认启动 Streamlit 前端
CMD ["python", "main.py", "frontend", "--port", "8501"]
