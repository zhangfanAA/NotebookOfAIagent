"""
JWT 认证模块
"""

import os
import datetime
import jwt
import bcrypt
from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("api.auth")

SECRET_KEY = os.environ.get("JWT_SECRET", "learning-assistant-jwt-secret-change-in-prod")
ALGORITHM = "HS256"
EXPIRE_HOURS = 24


def create_token(user_id: int, username: str, role: int = 1) -> str:
    """创建 JWT token"""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=EXPIRE_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    验证 JWT token

    Returns:
        {"user_id": int, "username": str}

    Raises:
        jwt.InvalidTokenError: token 无效或过期
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def authenticate_user(username: str, password: str) -> dict | None:
    """
    验证用户名密码

    Returns:
        {"id": int, "username": str, "role": int} 或 None
        被封号时返回 {"banned": True}
    """
    db = DBManager()
    user = db.fetch_one("SELECT id, username, password_hash, role, banned FROM users WHERE username = %s", (username,))
    if not user:
        return None
    if user.get("banned"):
        return {"banned": True}
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return None
    return {"id": user["id"], "username": user["username"], "role": user["role"]}
