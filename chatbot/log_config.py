# 日志配置函数已弃置
import logging
import os
import sys

def setup_logger(log_filename="bot.log"):
    """
    配置全局日志系统：
    1. 同时输出到控制台 (Console) 和 文件 (bot.log)
    2. 格式包含毫秒级时间戳，模仿 Python 默认报错风格
    3. 自动捕获异常堆栈 (Traceback)
    """

    # 确定日志文件路径：放在当前运行脚本的目录下
    # 如果是直接运行 chatbot.py，log 就会在 chatbot.py 旁边
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, log_filename)

    # 定义日志格式
    # %(asctime)s: 时间
    # %(name)s: 模块名 (如 __main__, job_database)
    # %(levelname)s: 级别 (INFO, ERROR)
    # %(message)s: 消息内容
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # 定义时间格式：2026-03-15 13:08:36,576 (保留3位毫秒)
    date_format = '%Y-%m-%d %H:%M:%S,%f'[:-3]

    # 获取根 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # 设置最低记录级别为 INFO

    # 清除可能已存在的 handler (防止重复打印，特别是在热重载时)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 创建 Formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # 1. 文件处理器 (FileHandler) -> 写入 bot.log
    # encoding='utf-8' 防止中文乱码
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 2. 控制台处理器 (StreamHandler) -> 显示在 PyCharm 终端
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 添加处理器到 logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 【可选】降低第三方库噪音 (httpx, telegram 等)，只让它们报告错误，避免 log 文件太大
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # 记录一条启动信息，确认配置成功
    logger.info(f"Logger initialized. Logs saved to: {log_path}")

    return logger


# 如果直接运行这个文件，也可以测试一下
if __name__ == "__main__":
    setup_logger()
    logging.info("测试：这是一条普通信息")
    logging.warning("测试：这是一条警告信息")
    try:
        raise ValueError("测试：这是一个故意制造的错误")
    except Exception:
        logging.exception("测试：记录异常堆栈")