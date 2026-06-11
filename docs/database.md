# 数据库说明

## 连接信息

```
mysql -u root -p
```

本项目使用数据库 `project`，在该数据库下进行表的创建和管理。

## 数据表

系统在 `Backend/src/database/db_manager.py` 的 `init_tables()` 方法中自动创建和迁移数据表。

### 用户与认证

| 表名 | 说明 |
|------|------|
| `users` | 用户表（id, username, password_hash, role, banned, balance, cloud_api_key, cloud_base_url, cloud_model, last_online_at） |

### 会话与消息

| 表名 | 说明 |
|------|------|
| `sessions` | 会话表（session_id, user_id, title, notes, is_active） |
| `messages` | 消息表（id, session_id, role, content, sources, reasoning, confidence, loop_count） |

### 文档管理

| 表名 | 说明 |
|------|------|
| `documents` | 文档表（id, user_id, file_name, file_path, file_type, file_size, chunks_count, status, full_text） |

### 学习功能

| 表名 | 说明 |
|------|------|
| `knowledge_diagnosis` | 知识诊断表（id, session_id, topic, question_count, suggestion） |
| `favorites` | 收藏表（id, session_id, message_id, content, question） |
| `reading_progress` | 阅读进度表（id, user_id, file_name, current_page, total_pages, is_finished） |
| `bookmarks` | 书签表（id, user_id, file_name, page_number, title, note） |
| `tags` | 标签表（id, name, color） |
| `message_tags` | 消息标签关联表（message_id, tag_id） |

### 保存内容

| 表名 | 说明 |
|------|------|
| `saved_mindmaps` | 思维导图表（id, user_id, title, output_type, content, mermaid_code, file_names） |
| `saved_quizzes` | 测验表（id, user_id, title, questions, score_correct, score_total, difficulty, file_names） |
| `saved_flashcards` | 闪卡表（id, user_id, title, cards, file_names） |

### 系统配置

| 表名 | 说明 |
|------|------|
| `settings` | 设置表（key, value） |
| `global_config` | 全局配置表（num, llm_provider, api_key, base_url, model） |
| `usage_logs` | 使用记录表（id, user_id, model, prompt_tokens, completion_tokens, cache_hit/miss_tokens, cost） |

### 通信与文件

| 表名 | 说明 |
|------|------|
| `user_messages` | 站内信表（id, from_user_id, to_user_id, content, is_read） |
| `download_files` | 文件下载表（id, file_name, file_path, file_size, uploaded_by） |

## 自动迁移

`DBManager.init_tables()` 自动处理：
- 创建缺失的数据表
- 添加缺失的列
- 创建 admin 默认用户
- 归档无主数据到 admin 用户
