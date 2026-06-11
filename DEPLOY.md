# 智能学习助手 — 部署指南

## 系统架构

```
┌──────────────┐     ┌──────────────────────────────────┐     ┌──────────────┐
│  Next.js     │────▶│  FastAPI 后端                     │────▶│  MySQL 8.0   │
│  前端 :3000  │     │  :8000                            │     │  :3306       │
└──────────────┘     │  ┌─────────────┐ ┌─────────────┐ │     └──────────────┘
                     │  │ REST API    │ │ Agent API   │ │
                     │  │ /api/chat   │ │ /api/agent  │ │     ┌──────────────┐
                     │  └─────────────┘ └──────┬──────┘ │────▶│  ChromaDB    │
                     │                         │        │     │  (向量存储)   │
                     │              ┌───────────┴──────┐ │     └──────────────┘
                     │              │ Supervisor Agent  │ │
                     │              │ (LangGraph)       │ │     ┌──────────────┐
                     │              └───────────┬──────┘ │────▶│  Ollama/     │
                     │              ┌───────────┴──────┐ │     │  DeepSeek    │
                     │              │ MCP Server 层     │ │     └──────────────┘
                     │              │ (stdio 子进程)    │ │
                     │              └──────────────────┘ │
                     └──────────────────────────────────┘

┌──────────────────────────┐
│  OCR 服务器（独立项目）    │
│  OCRServer/  :8001       │
│  后端通过 HTTP 代理调用    │
└──────────────────────────┘
```

MCP Server 作为子进程由 Supervisor Agent 按需启动，无需独立容器。
OCR Server 为独立项目，Backend 通过 httpx 代理转发 `/api/ocr/cloud` 请求。

---

## 方式一：Docker Compose 部署（推荐）

### 1. 准备服务器

确保服务器已安装：
- Docker
- Docker Compose

### 2. 上传项目到服务器

```bash
# 方式一：使用 git
git clone <your-repo-url>
cd demo1

# 方式二：使用 scp
scp -r ./demo1 user@server:/path/to/
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必须修改的配置：**
- `DB_PASSWORD` — 数据库密码
- `DEEPSEEK_API_KEY` — DeepSeek API 密钥
- `JWT_SECRET` — JWT 认证密钥（随机字符串）

### 4. 运行部署脚本

```bash
chmod +x Backend/deploy.sh
./Backend/deploy.sh
```

### 5. 访问应用

部署完成后，访问：
- **前端**: `http://服务器IP:3000`
- **API 后端**: `http://服务器IP:8000`
- **API 文档**: `http://服务器IP:8000/docs`

**默认管理员账号：**
- 用户名: `admin`
- 密码: `zf051110`

---

## 方式二：VPS 手动部署（exeFront 桌面端后端）

适用于 exeFront 桌面端场景，服务器只跑后端，OCR/PDF 解析在客户端本地完成。

```bash
# 1. 上传项目到服务器
scp -r ./demo1 root@你的服务器IP:/opt/learning-assistant/

# 2. SSH 登录服务器执行部署
ssh root@你的服务器IP
cd /opt/learning-assistant
sudo bash Backend/deploy.sh
```

脚本会自动：
- 安装 Python3 + MySQL
- 创建数据库和用户
- 创建 Python 虚拟环境并安装依赖
- 生成 .env 配置（数据库密码、JWT 密钥自动生成）
- 创建 systemd 服务，开机自启

**架构：**
```
用户电脑                          VPS 服务器
┌─────────────────┐              ┌──────────────────┐
│ EXEFront 桌面端  │─── HTTP ───→│ FastAPI (8000)    │
│ + 本地 PaddleOCR │              │ + MySQL           │
│ + PyMuPDF       │              │ + 向量库 ChromaDB  │
└─────────────────┘              └──────────────────┘
```

---

## 方式三：本地开发

```bash
# 后端
cd Backend
pip install -r requirements.txt
python main.py init-db    # 初始化数据库
python main.py api        # 启动后端 (localhost:8000)

# 前端
cd Frontend
npm install
npm run dev               # 启动前端 (localhost:3000)

# OCR 服务器（可选，云端 OCR 需要）
cd OCRServer
pip install -r requirements.txt
python main.py            # 启动 OCR 服务 (localhost:8001)
```

---

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| mysql | 3306 | MySQL 数据库 |
| api | 8000 | FastAPI 后端（含 Supervisor Agent + MCP Server） |
| frontend | 3000 | Next.js 前端 |
| ocr-server | 8001 | OCR 服务器（独立项目，可选） |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_HOST` | MySQL 主机 | localhost |
| `DB_PORT` | MySQL 端口 | 3306 |
| `DB_USER` | MySQL 用户 | root |
| `DB_PASSWORD` | 数据库密码 | 1234 |
| `DB_NAME` | 数据库名称 | project |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | - |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | https://api.deepseek.com/v1 |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | http://localhost:11434 |
| `OLLAMA_MODEL` | Ollama 模型名称 | qwen2.5:7b-instruct |
| `JWT_SECRET` | JWT 认证密钥 | - |
| `APP_HOST` | 服务监听地址 | 0.0.0.0 |
| `APP_PORT` | API 后端端口 | 8000 |
| `FRONTEND_PORT` | Next.js 前端端口 | 3000 |
| `OCR_SERVER_URL` | OCR 服务器地址 | http://localhost:8001 |

---

## Ollama 配置

如果要在服务器上使用 Ollama：

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull qwen2.5:7b-instruct

# 启动 Ollama 服务
ollama serve
```

然后在 `.env` 中设置：
```
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 数据持久化

以下数据会持久化保存：
- **MySQL 数据**: Docker volume `mysql_data`
- **上传的 PDF**: `./uploads/`
- **向量数据库**: `./data/chroma_db/`
- **日志文件**: `./logs/`
- **配置文件**: `./Backend/config/`

---

## 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看所有日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 重新构建并启动
docker-compose up -d --build

# 进入容器
docker exec -it la-api bash
```

---

## 故障排查

### 1. 服务启动失败

```bash
# 查看日志
docker-compose logs api

# 检查数据库连接
docker exec -it la-mysql mysql -u root -p
```

### 2. 端口被占用

修改 `.env` 中的端口配置：
```
APP_PORT=8001
FRONTEND_PORT=3001
```

### 3. 数据库连接失败

确保 MySQL 服务已启动并健康：
```bash
docker-compose ps
docker-compose logs mysql
```

### 4. Ollama 连接失败

如果 Ollama 在宿主机运行，确保：
1. Ollama 服务已启动
2. 防火墙允许 11434 端口
3. `.env` 中 `OLLAMA_BASE_URL` 配置正确

### 5. OCR 服务不可用

OCR 服务为独立项目，云端 OCR 需要单独启动：
```bash
cd OCRServer
pip install -r requirements.txt
python main.py  # 端口 8001
```

Backend 通过 `OCR_SERVER_URL` 环境变量连接 OCR 服务。如果 OCR 服务未启动，云端 OCR 功能不可用，但不影响其他功能。

---

## 生产环境建议

1. **修改默认密码**: 部署后立即修改管理员密码
2. **配置 HTTPS**: 使用 Nginx 反向代理并配置 SSL
3. **定期备份**: 备份 MySQL 数据和上传的文件
4. **监控日志**: 定期检查日志文件
5. **资源限制**: 根据服务器配置调整 Docker 资源限制

---

## Nginx 反向代理配置（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Next.js 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # API 后端（含 /api/chat, /api/agent 等所有端点）
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        # SSE 流式响应需要禁用缓冲
        proxy_buffering off;
        proxy_cache off;
    }
}
```
