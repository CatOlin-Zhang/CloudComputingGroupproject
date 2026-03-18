import os
import configparser
from pathlib import Path

# 获取当前文件 (config.py) 所在的绝对路径
CURRENT_FILE_DIR = Path(__file__).resolve().parent

# 获取项目根目录 (即 chatbot 的父目录)
PROJECT_ROOT = CURRENT_FILE_DIR.parent

EXCEL_FILE_PATH = PROJECT_ROOT / "JobData" / "Jobdata.xlsx"

# 向量数据库/缓存保存路径 (保存在 chatbot 目录下)
VECTOR_STORE_PATH = CURRENT_FILE_DIR / "vector_store_db"

# --- 调试打印 (启动时会在控制台显示，确认路径是否正确) ---
print(f" [Config Debug] 当前脚本目录：{CURRENT_FILE_DIR}")
print(f" [Config Debug] 项目根目录：{PROJECT_ROOT}")
print(f" [Config Debug] 正在查找 Excel 路径：{EXCEL_FILE_PATH}")

if not EXCEL_FILE_PATH.exists():
    print(f" [Config Error] 文件不存在！请检查路径或文件名大小写。")
    # 列出 JobData 目录下的所有文件，排查文件名是否拼写错误
    job_data_dir = PROJECT_ROOT / "JobData"
    if job_data_dir.exists():
        print(f" [Config Debug] JobData 目录下的文件有：{os.listdir(job_data_dir)}")
    else:
        print(f" [Config Debug] JobData 目录本身都不存在！")
else:
    print(f" [Config Success] Excel 文件找到！")


# --- 2. RAG 检索策略配置 ---
class RAGConfig:
    TOP_K = 3  #最多返回TOP_K个结果
    SIMILARITY_THRESHOLD = 0.05 #最低相似度分数
    NGRAM_RANGE = (2, 4)
    MAX_FEATURES = 5000
    INCLUDE_METADATA_IN_CONTEXT = True


# --- 3. LLM / API 行为配置 ---
class LLMConfig:
    SYSTEM_PROMPT_TEMPLATE = """
    You are a professional Career Assistant for university students.

    YOUR TASK:
    Answer the user's question using SOLELY the provided "Retrieved Job Data".

    CRITICAL RULES:
    1. GROUNDEDNESS: Never invent job requirements, salaries, or dates not present in the data.
    2. MISSING INFO: If the data does not contain the answer, explicitly state: "根据现有资料，未找到该具体信息。"
    3. NO MATCH: If the retrieved data is empty or irrelevant, tell the user: "未在数据库中找到匹配的职位，建议尝试搜索具体的公司名、城市或岗位关键词。"
    4. FORMATTING: When listing jobs, always include the [Application Link] if available.
    5. TONE: Professional, concise, and helpful.

    --- Retrieved Job Data ---
    {context}
    --- End of Data ---
    """

    TEMPERATURE = 1
    MAX_TOKENS = 800
    TOP_P = 0.9
    TIMEOUT = 40


# --- 4. Telegram Bot 配置 ---
class BotConfig:
    LOADING_TEXT = " 正在检索职位库并分析..."
    FILE_RECEIVED_TEXT = " 收到简历 `{file_name}`。目前系统暂不支持直接解析文件内容，请直接告诉我您的**专业、意向城市和期望职位**，我将为您精准匹配。"


# --- 5. 辅助函数：加载 .ini 中的敏感信息 ---
def load_secrets():
    config = configparser.ConfigParser()
    ini_path = CURRENT_FILE_DIR / "config.ini"
    if not ini_path.exists():
        raise FileNotFoundError("config.ini not found!")

    config.read(ini_path, encoding='utf-8')

    return {
        "TELEGRAM_TOKEN": config.get('TELEGRAM', 'ACCESS_TOKEN'),
        "CHATGPT_API_KEY": config.get('CHATGPT', 'API_KEY'),
        "CHATGPT_BASE_URL": config.get('CHATGPT', 'BASE_URL'),
        "CHATGPT_MODEL": config.get('CHATGPT', 'MODEL'),
        "CHATGPT_API_VER": config.get('CHATGPT', 'API_VER'),
    }