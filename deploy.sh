#!/bin/bash
# ============================================
# 智能学习助手 — Linux 服务器部署脚本
# ============================================
# 使用方法: chmod +x deploy.sh && ./deploy.sh
#
# 架构: MySQL + FastAPI(含 MCP/Supervisor) + Next.js
# ============================================

set -e

echo "=========================================="
echo "  智能学习助手 — 服务器部署"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker 安装完成，请重新登录后运行此脚本"
    exit 0
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，正在安装..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose 安装完成"
fi

echo "✅ Docker 版本: $(docker --version)"
echo "✅ Docker Compose 版本: $(docker-compose --version)"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，正在从模板创建..."
    cp .env.example .env
    echo "📝 请编辑 .env 文件填写配置后重新运行此脚本"
    echo "   vim .env"
    exit 0
fi

echo ""
echo "=========================================="
echo "  开始部署..."
echo "=========================================="

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down 2>/dev/null || true

# 构建镜像
echo "🔨 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 15

# 检查服务状态
echo ""
echo "=========================================="
echo "  服务状态"
echo "=========================================="
docker-compose ps

# 获取服务器 IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "📌 访问地址:"
echo "   前端: http://${SERVER_IP}:3000"
echo "   API:  http://${SERVER_IP}:8000"
echo "   API 文档: http://${SERVER_IP}:8000/docs"
echo ""
echo "📌 API 端点:"
echo "   传统聊天: POST /api/chat/stream"
echo "   Agent:    POST /api/agent/stream"
echo ""
echo "📌 MCP Server（由 Agent 自动启动，无需手动操作）:"
echo "   RAG:      python -m src.mcp_servers.rag_server"
echo "   学习工具: python -m src.mcp_servers.learning_tools_server"
echo "   OCR:      python -m src.mcp_servers.ocr_server"
echo ""
echo "📌 常用命令:"
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose down"
echo "   重启服务: docker-compose restart"
echo "   查看状态: docker-compose ps"
echo ""
echo "📌 默认管理员账号:"
echo "   用户名: admin"
echo "   密码: zf051110"
echo ""
