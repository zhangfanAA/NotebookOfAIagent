"""
智能学习助手 — MySQL 数据库连接池管理
负责: FULL
任务: TASK-DATA-005

提供统一的数据库连接管理，支持连接池、参数化查询、表初始化。
"""

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

from src.config import get_config
from src.logger import get_logger

logger = get_logger("database.db_manager")

# 建表 SQL
TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            user_id INT DEFAULT NULL,
            title VARCHAR(255) DEFAULT '新会话',
            notes TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_active TINYINT(1) DEFAULT 1,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            role ENUM('user', 'assistant', 'system') NOT NULL,
            content TEXT NOT NULL,
            sources JSON DEFAULT NULL,
            reasoning TEXT DEFAULT NULL,
            confidence FLOAT DEFAULT NULL,
            loop_count INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_created_at (created_at),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "documents": """
        CREATE TABLE IF NOT EXISTS documents (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_type VARCHAR(20) NOT NULL,
            file_size BIGINT DEFAULT 0,
            chunks_count INT DEFAULT 0,
            status ENUM('processing', 'ready', 'error') DEFAULT 'processing',
            error_message TEXT DEFAULT NULL,
            full_text LONGTEXT DEFAULT NULL,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_status (status),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "knowledge_diagnosis": """
        CREATE TABLE IF NOT EXISTS knowledge_diagnosis (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            topic VARCHAR(255) NOT NULL,
            question_count INT DEFAULT 1,
            last_asked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            suggestion TEXT DEFAULT NULL,
            UNIQUE KEY uk_session_topic (session_id, topic),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "favorites": """
        CREATE TABLE IF NOT EXISTS favorites (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            message_id BIGINT DEFAULT NULL,
            content TEXT NOT NULL,
            question TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "reading_progress": """
        CREATE TABLE IF NOT EXISTS reading_progress (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            file_name VARCHAR(255) NOT NULL,
            current_page INT DEFAULT 0,
            total_pages INT DEFAULT 0,
            is_finished TINYINT(1) DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_user_file (user_id, file_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "bookmarks": """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            file_name VARCHAR(255) NOT NULL,
            page_number INT NOT NULL,
            title VARCHAR(255) DEFAULT NULL,
            note TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_file_name (file_name),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "tags": """
        CREATE TABLE IF NOT EXISTS tags (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            color VARCHAR(20) DEFAULT '#5ac8fa',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "message_tags": """
        CREATE TABLE IF NOT EXISTS message_tags (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            message_id BIGINT NOT NULL,
            tag_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_msg_tag (message_id, tag_id),
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "saved_mindmaps": """
        CREATE TABLE IF NOT EXISTS saved_mindmaps (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            title VARCHAR(255) NOT NULL,
            output_type ENUM('mindmap', 'notes') NOT NULL,
            content LONGTEXT NOT NULL,
            mermaid_code TEXT DEFAULT NULL,
            file_names JSON DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_output_type (output_type),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "saved_quizzes": """
        CREATE TABLE IF NOT EXISTS saved_quizzes (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            title VARCHAR(255) NOT NULL,
            questions JSON NOT NULL,
            score_correct INT DEFAULT 0,
            score_total INT DEFAULT 0,
            difficulty VARCHAR(20) DEFAULT 'medium',
            file_names JSON DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "saved_flashcards": """
        CREATE TABLE IF NOT EXISTS saved_flashcards (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            title VARCHAR(255) NOT NULL,
            cards JSON NOT NULL,
            file_names JSON DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "settings": """
        CREATE TABLE IF NOT EXISTS settings (
            `key` VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
}


class DBManager:
    """
    MySQL 连接池管理器

    使用 DBUtils PooledDB 实现连接池，支持参数化查询防止 SQL 注入。
    """

    def __init__(self, config: dict = None):
        """
        初始化连接池

        Args:
            config: 数据库配置字典，为 None 时从全局配置读取
        """
        if config is None:
            config = get_config()["database"]

        self._pool = PooledDB(
            creator=pymysql,
            maxconnections=config.get("pool_size", 5),
            mincached=1,
            maxcached=config.get("pool_size", 5),
            blocking=True,
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        logger.info(
            "数据库连接池初始化完成: %s@%s:%d/%s (pool_size=%d)",
            config["user"],
            config["host"],
            config["port"],
            config["database"],
            config.get("pool_size", 5),
        )

    def get_connection(self):
        """获取数据库连接（从连接池）"""
        return self._pool.connection()

    def init_tables(self):
        """初始化所有数据表"""
        import bcrypt

        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                for table_name, ddl in TABLES.items():
                    cursor.execute(ddl)
                    logger.info("表 %s 初始化完成", table_name)

                # 迁移：给 documents 表加 full_text 列（已有则跳过）
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' AND COLUMN_NAME = 'full_text'"
                )
                if cursor.fetchone()["cnt"] == 0:
                    cursor.execute("ALTER TABLE documents ADD COLUMN full_text LONGTEXT DEFAULT NULL")
                    logger.info("迁移: documents 表已添加 full_text 列")

                # 迁移：给已有表加 user_id 列（升级场景）
                tables_needing_user_id = [
                    "sessions", "documents", "reading_progress",
                    "bookmarks", "saved_mindmaps", "saved_quizzes", "saved_flashcards",
                ]
                for tbl in tables_needing_user_id:
                    cursor.execute(
                        "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'user_id'",
                        (tbl,),
                    )
                    if cursor.fetchone()["cnt"] == 0:
                        cursor.execute(f"ALTER TABLE `{tbl}` ADD COLUMN user_id INT DEFAULT NULL")
                        cursor.execute(f"ALTER TABLE `{tbl}` ADD INDEX idx_user_id (user_id)")
                        logger.info("迁移: %s 表已添加 user_id 列", tbl)

                # 创建 admin 用户（密码 bcrypt 加密）
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                admin_row = cursor.fetchone()
                if admin_row:
                    admin_id = admin_row["id"]
                    logger.info("admin 用户已存在: id=%d", admin_id)
                else:
                    password_hash = bcrypt.hashpw("zf051110".encode(), bcrypt.gensalt()).decode()
                    cursor.execute(
                        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                        ("admin", password_hash),
                    )
                    admin_id = cursor.lastrowid
                    logger.info("admin 用户已创建: id=%d", admin_id)

                # 将所有现有数据归于 admin 用户
                for tbl in tables_needing_user_id:
                    cursor.execute(f"UPDATE `{tbl}` SET user_id = %s WHERE user_id IS NULL", (admin_id,))
                    affected = cursor.rowcount
                    if affected > 0:
                        logger.info("迁移: %s 表 %d 条记录已归于 admin", tbl, affected)

                # 初始化默认设置（INSERT IGNORE 避免重复）
                default_settings = [
                    ("llm_provider", "local"),
                    ("cloud_base_url", "https://api.deepseek.com/v1"),
                    ("cloud_api_key", ""),
                    ("cloud_model", "deepseek-chat"),
                ]
                for key, value in default_settings:
                    cursor.execute(
                        "INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s, %s)",
                        (key, value),
                    )

            logger.info("所有数据表初始化完成")
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = None) -> int:
        """
        执行写操作（INSERT/UPDATE/DELETE）

        Returns:
            受影响的行数
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                return affected
        finally:
            conn.close()

    def execute_returning_id(self, sql: str, params: tuple = None) -> int:
        """
        执行 INSERT 并返回自增 ID

        Returns:
            新插入记录的自增 ID
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.lastrowid
        finally:
            conn.close()

    def fetch_one(self, sql: str, params: tuple = None) -> dict:
        """
        查询单条记录

        Returns:
            字典形式的记录，无记录时返回 None
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: tuple = None) -> list:
        """
        查询多条记录

        Returns:
            字典列表，无记录时返回空列表
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def execute_many(self, sql: str, params_list: list) -> int:
        """
        批量执行写操作

        Returns:
            受影响的总行数
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.executemany(sql, params_list)
                return affected
        finally:
            conn.close()
