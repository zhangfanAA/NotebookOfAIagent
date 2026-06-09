# ============================================
# 智能学习助手 — Makefile
# ============================================
# 常用命令快捷入口
# ============================================

.PHONY: install init-db frontend api test docker-up docker-down clean

# 安装依赖
install:
	pip install -r requirements.txt

# 初始化数据库表
init-db:
	python main.py init-db

# 启动 Streamlit 前端
frontend:
	python main.py frontend

# 启动 FastAPI 后端
api:
	python main.py api

# 运行测试
test:
	pytest tests/ -v

# Docker 一键启动
docker-up:
	docker-compose up -d

# Docker 停止
docker-down:
	docker-compose down

# Docker 查看日志
docker-logs:
	docker-compose logs -f

# 清理临时文件
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf logs/*.log
