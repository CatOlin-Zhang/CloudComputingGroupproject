# main.py

import logging
import os
import sys
from job_database import init_database, load_jobs_from_excel
from chatbot import main as run_bot

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_environment():
    """设置环境，初始化数据库并导入数据"""
    logger.info("Setting up environment...")

    # 1. 初始化数据库表
    init_database()
    logger.info("Database initialized.")

    # 2.使用绝对路径定位文件
    # 获取 main.py 所在的绝对目录 (例如: .../CloudComputingGroupproject/chatbot)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 定义要搜索的文件夹列表
    # 1. main.py 当前目录
    # 2. 同级目录下的 JobData 文件夹 (base_dir 的父目录 / JobData)
    parent_dir = os.path.dirname(base_dir)
    search_paths = [
        base_dir,
        os.path.join(parent_dir, 'JobData')
    ]

    logger.info(f"Searching for Excel files in: {search_paths}")

    all_found_files = []

    for path in search_paths:
        if os.path.exists(path):
            logger.info(f"Checking path: {path}")
            try:
                files_in_dir = os.listdir(path)
                logger.debug(f"Files in {path}: {files_in_dir}")

                for f in files_in_dir:
                    if f.endswith('.xlsx') and not f.startswith('~$'):
                        full_path = os.path.join(path, f)
                        all_found_files.append(full_path)
            except Exception as e:
                logger.error(f"Error listing directory {path}: {e}")
        else:
            logger.warning(f"Path does not exist: {path}")

    if all_found_files:
        logger.info(f"Found Excel files to process: {all_found_files}")
        total_imported = 0

        for excel_file in all_found_files:
            try:
                logger.info(f"Processing {excel_file}...")
                count = load_jobs_from_excel(excel_file)
                total_imported += count
                logger.info(f"-> Imported {count} jobs from {excel_file}.")
            except Exception as e:
                logger.error(f"Failed to import {excel_file}: {e}", exc_info=True)

        logger.info(f"Total jobs imported in this session: {total_imported}")
    else:
        logger.error("No Excel files found! Please check file name and path.")
        logger.info("Using existing database (might be empty).")


def main():
    """主函数：一键启动"""
    try:
        # 步骤 1: 数据处理
        setup_environment()

        # 步骤 2: 启动机器人
        logger.info("=" * 30)
        logger.info("Starting Telegram Bot...")
        logger.info("=" * 30)
        run_bot()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()