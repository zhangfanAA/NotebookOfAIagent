"""
用户/余额/使用记录仓库
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.user_repo")


class UserRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def get_user(self, user_id: int) -> dict | None:
        """查询单个用户（含 role, balance, banned, last_online_at）"""
        return self.db.fetch_one(
            "SELECT id, username, role, banned, balance, cloud_api_key, cloud_base_url, cloud_model, last_online_at, created_at FROM users WHERE id = %s",
            (user_id,),
        )

    def set_banned(self, user_id: int, banned: bool):
        """封号/解封"""
        self.db.execute("UPDATE users SET banned = %s WHERE id = %s", (1 if banned else 0, user_id))
        logger.info("用户 %d 已%s", user_id, "封禁" if banned else "解封")

    def update_last_online(self, user_id: int):
        """更新最后上线时间"""
        self.db.execute("UPDATE users SET last_online_at = NOW() WHERE id = %s", (user_id,))

    def get_user_by_username(self, username: str) -> dict | None:
        return self.db.fetch_one(
            "SELECT id, username, role, balance, cloud_api_key, cloud_base_url, cloud_model, created_at FROM users WHERE username = %s",
            (username,),
        )

    def list_users(self) -> list[dict]:
        """查询所有用户"""
        return self.db.fetch_all(
            "SELECT id, username, role, banned, balance, cloud_api_key, cloud_base_url, cloud_model, last_online_at, created_at FROM users ORDER BY id"
        )

    def update_balance(self, user_id: int, amount: float) -> float:
        """更新余额（正数加、负数减），返回新余额"""
        self.db.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (amount, user_id),
        )
        row = self.db.fetch_one("SELECT balance FROM users WHERE id = %s", (user_id,))
        return float(row["balance"]) if row else 0.0

    def set_balance(self, user_id: int, balance: float):
        """直接设置余额"""
        self.db.execute(
            "UPDATE users SET balance = %s WHERE id = %s",
            (balance, user_id),
        )

    def add_usage_log(
        self,
        user_id: int,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cache_hit_tokens: int,
        cache_miss_tokens: int,
        cost: float,
    ):
        """添加使用记录"""
        self.db.execute(
            "INSERT INTO usage_logs (user_id, model, prompt_tokens, completion_tokens, "
            "cache_hit_tokens, cache_miss_tokens, cost) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, model, prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens, cost),
        )

    def get_user_api_settings(self, user_id: int) -> dict | None:
        """查询用户的 API 配置（cloud_api_key, cloud_base_url, cloud_model）"""
        return self.db.fetch_one(
            "SELECT cloud_api_key, cloud_base_url, cloud_model FROM users WHERE id = %s",
            (user_id,),
        )

    def update_user_api_settings(self, user_id: int, cloud_api_key: str = None,
                                  cloud_base_url: str = None, cloud_model: str = None):
        """更新用户的 API 配置字段（只更新非 None 的字段）"""
        updates = []
        params = []
        if cloud_api_key is not None:
            updates.append("cloud_api_key = %s")
            params.append(cloud_api_key)
        if cloud_base_url is not None:
            updates.append("cloud_base_url = %s")
            params.append(cloud_base_url)
        if cloud_model is not None:
            updates.append("cloud_model = %s")
            params.append(cloud_model)
        if not updates:
            return
        params.append(user_id)
        self.db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
            tuple(params),
        )

    def get_usage_logs(self, user_id: int = None, page: int = 1, size: int = 20) -> dict:
        """分页查询使用记录"""
        offset = (page - 1) * size
        if user_id:
            rows = self.db.fetch_all(
                "SELECT * FROM usage_logs WHERE user_id = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (user_id, size, offset),
            )
            count_row = self.db.fetch_one(
                "SELECT COUNT(*) AS total FROM usage_logs WHERE user_id = %s",
                (user_id,),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM usage_logs ORDER BY id DESC LIMIT %s OFFSET %s",
                (size, offset),
            )
            count_row = self.db.fetch_one("SELECT COUNT(*) AS total FROM usage_logs")

        return {
            "items": rows,
            "total": count_row["total"] if count_row else 0,
            "page": page,
            "size": size,
        }
