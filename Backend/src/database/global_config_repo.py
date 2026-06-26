"""
全局配置仓库
num=1 全局云端配置, num=2 余额模型配置, num=3 系统设置, num=4 余额OCR配置
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
        更新指定 num 的字段（只更新非 None 的字段，行不存在时自动插入）
        """
        # 确保行存在
        existing = self.db.fetch_one("SELECT num FROM global_config WHERE num = %s", (num,))
        if not existing:
            self.db.execute(
                "INSERT INTO global_config (num, llm_provider, api_key, base_url, model) VALUES (%s, '', '', '', '')",
                (num,),
            )

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

    def get_paddle_ocr_enabled(self) -> bool:
        """获取 PaddleOCR 开关状态（网页端，向后兼容）"""
        return self.get_paddle_ocr_web_enabled()

    def set_paddle_ocr_enabled(self, enabled: bool):
        """设置 PaddleOCR 开关（网页端，向后兼容）"""
        self.set_paddle_ocr_web_enabled(enabled)

    def get_paddle_ocr_web_enabled(self) -> bool:
        """获取网页端 PaddleOCR 开关状态"""
        cfg = self.get(3)
        return cfg.get("base_url", "1") == "1"

    def set_paddle_ocr_web_enabled(self, enabled: bool):
        """设置网页端 PaddleOCR 开关"""
        self.update(3, base_url="1" if enabled else "0")
        logger.info("网页端 PaddleOCR 开关已设置为: %s", "开启" if enabled else "关闭")

    def get_paddle_ocr_app_enabled(self) -> bool:
        """获取桌面端 PaddleOCR 开关状态"""
        cfg = self.get(3)
        return cfg.get("model", "1") == "1"

    def set_paddle_ocr_app_enabled(self, enabled: bool):
        """设置桌面端 PaddleOCR 开关"""
        self.update(3, model="1" if enabled else "0")
        logger.info("桌面端 PaddleOCR 开关已设置为: %s", "开启" if enabled else "关闭")

    # ===== 余额 OCR 配置 (num=4) =====

    def get_balance_ocr_config(self) -> dict:
        """获取余额 OCR 配置"""
        cfg = self.get(4)
        return {
            "api_key": cfg.get("api_key", ""),
        }

    def update_balance_ocr_config(self, api_key: str = None):
        """更新余额 OCR 配置"""
        self.update(4, api_key=api_key)
        logger.info("余额 OCR 配置已更新")
