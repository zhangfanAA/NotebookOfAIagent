"""
智能学习助手 — 启动配置校验
负责: RAG
任务: 配置校验与启动检查

在应用启动时检查各组件是否正常，提前发现问题。
"""

import os
from src.config import get_config
from src.logger import get_logger

logger = get_logger("utils.startup_check")


def run_startup_checks() -> dict:
    """
    运行启动检查，返回各组件状态

    Returns:
        {
            "all_ok": bool,
            "checks": [
                {"name": str, "ok": bool, "message": str, "level": "info"|"warn"|"error"}
            ]
        }
    """
    config = get_config()
    checks = []

    # 1. 数据库配置
    db_config = config.get("database", {})
    if db_config.get("host") and db_config.get("database"):
        checks.append({
            "name": "MySQL 配置",
            "ok": True,
            "message": f"{db_config['host']}:{db_config.get('port', 3306)}/{db_config['database']}",
            "level": "info",
        })
    else:
        checks.append({
            "name": "MySQL 配置",
            "ok": False,
            "message": "数据库配置不完整",
            "level": "error",
        })

    # 2. DeepSeek API Key
    api_key = config.get("llm", {}).get("fallback", {}).get("api_key", "")
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        checks.append({
            "name": "DeepSeek API",
            "ok": True,
            "message": f"已配置 ({masked})",
            "level": "info",
        })
    else:
        checks.append({
            "name": "DeepSeek API",
            "ok": False,
            "message": "未配置 API Key（云端降级不可用）",
            "level": "warn",
        })

    # 3. 向量库目录
    persist_dir = config.get("vector_store", {}).get("persist_dir", "")
    if persist_dir:
        os.makedirs(persist_dir, exist_ok=True)
        if os.path.isdir(persist_dir):
            checks.append({
                "name": "向量库目录",
                "ok": True,
                "message": persist_dir,
                "level": "info",
            })
        else:
            checks.append({
                "name": "向量库目录",
                "ok": False,
                "message": f"无法创建目录: {persist_dir}",
                "level": "error",
            })

    # 4. 嵌入模型检查（只检查配置，不加载模型）
    embedding_model = config.get("embedding", {}).get("model", "")
    if embedding_model:
        checks.append({
            "name": "嵌入模型配置",
            "ok": True,
            "message": embedding_model,
            "level": "info",
        })

    # 5. settings.yaml 存在性
    from pathlib import Path
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    if config_path.exists():
        checks.append({
            "name": "配置文件",
            "ok": True,
            "message": "settings.yaml 已加载",
            "level": "info",
        })
    else:
        checks.append({
            "name": "配置文件",
            "ok": False,
            "message": "settings.yaml 不存在，使用默认配置",
            "level": "warn",
        })

    all_ok = all(c["ok"] for c in checks if c["level"] == "error")

    return {"all_ok": all_ok, "checks": checks}


def print_startup_report():
    """打印启动检查报告到控制台"""
    result = run_startup_checks()

    print("\n" + "=" * 50)
    print("  智能学习助手 — 启动检查")
    print("=" * 50)

    for check in result["checks"]:
        icon = {"info": "✅", "warn": "⚠️", "error": "❌"}.get(check["level"], "❓")
        print(f"  {icon} {check['name']}: {check['message']}")

    print("-" * 50)
    if result["all_ok"]:
        print("  ✅ 所有必要检查通过，系统就绪")
    else:
        print("  ⚠️  部分检查未通过，系统可能无法正常工作")
    print("=" * 50 + "\n")
