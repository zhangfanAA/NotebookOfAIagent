#!/bin/bash
# ============================================
# 智能学习助手 — VPS 后端部署脚本
# 用法: 上传项目到服务器后执行 sudo bash deploy.sh
# ============================================

set -e

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
DB_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)

echo "=========================================="
echo "  智能学习助手 — 后端部署"
echo "=========================================="
echo "  项目目录: ${PROJECT_DIR}"

# 1. 系统依赖
echo ""
echo "[1/5] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv mysql-server libmysqlclient-dev > /dev/null 2>&1
echo "  ✅ Python3 + MySQL 已安装"

# 2. MySQL
echo ""
echo "[2/5] 配置 MySQL..."
systemctl start mysql
systemctl enable mysql

mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS project CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'learner'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON project.* TO 'learner'@'localhost';
FLUSH PRIVILEGES;
EOF
echo "  ✅ 数据库 project 已创建"

# 3. Python 虚拟环境
echo ""
echo "[3/5] 创建 Python 环境..."
cd "${PROJECT_DIR}"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
# 服务端不需要 paddleocr（OCR 在客户端本地跑）
grep -v -E "paddle(paddle|ocr)" requirements.txt > /tmp/req-server.txt
pip install -q -r /tmp/req-server.txt
rm /tmp/req-server.txt
echo "  ✅ Python 依赖已安装（已跳过 PaddleOCR）"

# 4. 环境配置
echo ""
echo "[4/5] 生成配置..."
cat > .env <<EOF
DB_HOST=localhost
DB_PORT=3306
DB_USER=learner
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=project
JWT_SECRET=${JWT_SECRET}
APP_HOST=0.0.0.0
APP_PORT=8000
EOF

mkdir -p data/pdfs data/chroma_db
echo "  ✅ .env 已生成"

# 5. Systemd 服务
echo ""
echo "[5/5] 创建系统服务..."
cat > /etc/systemd/system/learning-assistant.service <<EOF
[Unit]
Description=Learning Assistant Backend
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/python -m uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable learning-assistant
systemctl start learning-assistant

# 获取服务器 IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "  服务状态:  systemctl status learning-assistant"
echo "  查看日志:  journalctl -u learning-assistant -f"
echo "  重启服务:  systemctl restart learning-assistant"
echo ""
echo "  数据库密码: ${DB_PASSWORD}"
echo "  JWT 密钥:   ${JWT_SECRET}"
echo "  （请妥善保管，已写入 ${PROJECT_DIR}/.env）"
echo ""
echo "  API 地址:  http://${SERVER_IP}:8000"
echo "  API 文档:  http://${SERVER_IP}:8000/docs"
echo ""
echo "  EXEFront 客户端配置:"
echo "  在 EXEFront/.env 中写入:"
echo "  VITE_API_URL=http://${SERVER_IP}:8000"
echo ""
echo "  默认管理员: admin / zf051110"
echo "=========================================="
