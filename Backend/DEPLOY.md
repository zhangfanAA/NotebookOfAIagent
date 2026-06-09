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
```

MCP Server 作为子进程由 Supervisor Agent 按需启动，无需独立容器。

## 快速部署（推荐）

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
chmod +x deploy.sh
./deploy.sh
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

## 手动部署

如果不想使用部署脚本，可以手动执行：

```bash
# 1. 配置环境变量
cp .env.production .env
vim .env

# 2. 构建并启动服务
docker-compose up -d

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f
```

---

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| mysql | 3306 | MySQL 数据库 |
| api | 8000 | FastAPI 后端（含 Supervisor Agent + MCP Server） |
| frontend | 3000 | Next.js 前端 |

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/chat/stream` | 传统 RAG 流式聊天 |
| `POST /api/agent/chat` | Supervisor Agent 非流式对话 |
| `POST /api/agent/stream` | Supervisor Agent 流式对话（tool_call/token/done 事件） |
| `GET /api/status` | 健康检查 |

**Supervisor Agent 请求格式：**
```json
{"question": "帮我总结文档内容", "session_id": "可选"}
```

**Supervisor Agent 流式事件：**
```json
{"type": "tool_call", "tool": "rag_query", "args": {"question": "..."}}
{"type": "tool_result", "tool": "rag_query", "content": "..."}
{"type": "token", "content": "根据文档..."}
{"type": "done"}
```

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

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DB_PASSWORD | 数据库密码 | 1234 |
| DB_NAME | 数据库名称 | project |
| DB_PORT | 数据库端口 | 3306 |
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | - |
| DEEPSEEK_BASE_URL | DeepSeek API 地址 | https://api.deepseek.com/v1 |
| OLLAMA_BASE_URL | Ollama 服务地址 | http://host.docker.internal:11434 |
| OLLAMA_MODEL | Ollama 模型名称 | qwen2.5:7b-instruct |
| APP_PORT | API 后端端口 | 8000 |
| FRONTEND_PORT | Next.js 前端端口 | 3000 |
| JWT_SECRET | JWT 认证密钥 | - |

### Ollama 配置

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
- **上传的 PDF**: `./data/pdfs/`
- **向量数据库**: `./data/chroma_db/`
- **日志文件**: `./logs/`
- **配置文件**: `./config/`

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
