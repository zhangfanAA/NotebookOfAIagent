"""
全局配置仓库
num=1 全局云端配置, num=2 余额模型配置, num=3 系统设置
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.global_config_repo")


class GlobalConfigRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def get(self, num: int = 1) -> dict:
        """
        获取 global_config 中指定行的配置

        Args:
            num: 1=全局云端, 2=余额模型
        """
        row = self.db.fetch_one(
            "SELECT num, llm_provider, api_key, base_url, model FROM global_config WHERE num = %s",
            (num,),
        )
        if not row:
            return {
                "num": num,
                "llm_provider": "local",
                "api_key": "",
                "base_url": "",
                "model": "",
            }
        return row

    def update(self, num: int = 1, llm_provider: str = None, api_key: str = None,
               base_url: str = None, model: str = None):
        """
        更新指定 num 的字段（只更新非 None 的字段）

        Args:
            num: 1=全局云端, 2=余额模型
        """
        updates = []
        params = []
        if llm_provider is not None:
            updates.append("llm_provider = %s")
            params.append(llm_provider)
        if api_key is not None:
            updates.append("api_key = %s")
            params.append(api_key)
        if base_url is not None:
            updates.append("base_url = %s")
            params.append(base_url)
        if model is not None:
            updates.append("model = %s")
            params.append(model)
        if not updates:
            return
        params.append(num)
        self.db.execute(
            f"UPDATE global_config SET {', '.join(updates)} WHERE num = %s",
            tuple(params),
        )

    def get_allow_registration(self) -> bool:
        """获取注册开关状态"""
        cfg = self.get(3)
        return cfg.get("api_key", "1") == "1"

    def set_allow_registration(self, allowed: bool):
        """设置注册开关"""
        self.update(3, api_key="1" if allowed else "0")
        logger.info("注册开关已设置为: %s", "开启" if allowed else "关闭")
