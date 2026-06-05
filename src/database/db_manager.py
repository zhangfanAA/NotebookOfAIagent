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
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            title VARCHAR(255) DEFAULT '新会话',
            notes TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_active TINYINT(1) DEFAULT 1
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
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_type VARCHAR(20) NOT NULL,
            file_size BIGINT DEFAULT 0,
            chunks_count INT DEFAULT 0,
            status ENUM('processing', 'ready', 'error') DEFAULT 'processing',
            error_message TEXT DEFAULT NULL,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_status (status)
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
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                for table_name, ddl in TABLES.items():
                    cursor.execute(ddl)
                    logger.info("表 %s 初始化完成", table_name)
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
