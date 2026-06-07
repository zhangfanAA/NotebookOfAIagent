"""
智能学习助手 — 统一启动入口

Usage:
    python main.py frontend          # 启动 Streamlit 前端
    python main.py api               # 启动 FastAPI 后端
    python main.py init-db           # 初始化数据库表
    python main.py check             # 运行启动检查
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="智能学习助手")
    parser.add_argument(
        "command",
        choices=["frontend", "api", "init-db", "check"],
        help="启动模式",
    )
    parser.add_argument("--port", type=int, default=None, help="服务端口")
    parser.add_argument("--skip-check", action="store_true", help="跳过启动检查")
    args = parser.parse_args()

    # 启动检查
    if not args.skip_check and args.command in ("frontend", "api"):
        from src.utils.startup_check import print_startup_report
        print_startup_report()

    if args.command == "frontend":
        import subprocess
        port = args.port or 8501
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "src/frontend/app.py",
            "--server.port", str(port),
        ])

    elif args.command == "api":
        import uvicorn
        from src.config import get_config
        from src.database.db_manager import DBManager
        config = get_config()
        # 启动时自动初始化/迁移数据库表
        db = DBManager()
        db.init_tables()
        # 回填旧文档全文（延迟执行，等 uvicorn 完成 import 后再跑）
        import threading
        def _backfill():
            import time
            time.sleep(5)  # 等 uvicorn 和 torch 完全加载
            try:
                from src.rag.document_processor import DocumentProcessor
                DocumentProcessor().backfill_full_text()
            except Exception as e:
                print(f"回填全文失败: {e}")
        threading.Thread(target=_backfill, daemon=True).start()
        port = args.port or config["app"]["port"]
        uvicorn.run(
            "src.api.routes:app",
            host=config["app"]["host"],
            port=port,
            reload=config["app"]["debug"],
        )

    elif args.command == "init-db":
        from src.database.db_manager import DBManager
        db = DBManager()
        db.init_tables()
        print("数据库表初始化完成")

    elif args.command == "check":
        from src.utils.startup_check import print_startup_report
        print_startup_report()


if __name__ == "__main__":
    main()
