import os
import configparser
from pathlib import Path

# Get the absolute path of the directory where the current file (config.py) is located
CURRENT_FILE_DIR = Path(__file__).resolve().parent

# Get the project root directory (i.e., the parent of chatbot)
PROJECT_ROOT = CURRENT_FILE_DIR.parent

EXCEL_FILE_PATH = PROJECT_ROOT / "JobData" / "Jobdata.xlsx"

# Vector database/cache save path (saved in the chatbot directory)
VECTOR_STORE_PATH = CURRENT_FILE_DIR / "vector_store_db"

# --- Debug Print (Displayed in console at startup to confirm paths) ---
print(f" [Config Debug] Current script directory: {CURRENT_FILE_DIR}")
print(f" [Config Debug] Project root directory: {PROJECT_ROOT}")
print(f" [Config Debug] Looking for Excel path: {EXCEL_FILE_PATH}")

if not EXCEL_FILE_PATH.exists():
    print(f" [Config Error] File does not exist! Please check the path or filename case.")
    job_data_dir = PROJECT_ROOT / "JobData"
    if job_data_dir.exists():
        print(f" [Config Debug] Files in JobData directory: {os.listdir(job_data_dir)}")
    else:
        print(f" [Config Debug] JobData directory itself does not exist!")
else:
    print(f" [Config Success] Excel file found!")


# --- 2. RAG Retrieval Strategy Configuration  ---
class RAGConfig:
    # model can be used
    # 1. 'BAAI/bge-small-zh-v1.5'
    # 2. 'BAAI/bge-base-zh-v1.5'
    # 3. 'moka-ai/m3e-base'
    EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

    TOP_K = 3  # Recall volume, determines the maximum number of results returned

    SIMILARITY_THRESHOLD = 0.5  #Similarity threshold, values below this will not be recalled

    INCLUDE_METADATA_IN_CONTEXT = True

    # TF-IDF function wasted
    # NGRAM_RANGE = (2, 4)
    # MAX_FEATURES = 5000


# --- 3. LLM / API Behavior Configuration ---
class LLMConfig:
    SYSTEM_PROMPT_TEMPLATE = """
    You are a professional Career Assistant for university students.

    YOUR TASK:
    Answer the user's question using SOLELY the provided "Retrieved Job Data".

    CRITICAL RULES:
    1. GROUNDEDNESS: Never invent job requirements, salaries, or dates not present in the data.
    2. MISSING INFO: If the data does not contain the answer, explicitly state: "Based on available materials, the specific information was not found."
    3. NO MATCH: If the retrieved data is empty or irrelevant, tell the user: "No matching positions found in the database. Suggest trying to search for specific company names, cities, or job keywords."
    4. FORMATTING: When listing jobs, always include the [Application Link] if available.
    5. TONE: Professional, concise, and helpful.

    --- Retrieved Job Data ---
    {context}
    --- End of Data ---
    """

    TEMPERATURE = 1  # API force to be 1
    MAX_TOKENS = 800
    TOP_P = 0.9
    TIMEOUT = 45     # Time for response


# --- 4. Telegram Bot Configuration ---
class BotConfig:
    LOADING_TEXT = "  Analyzing semantic meaning in job database..."
    FILE_RECEIVED_TEXT = " Received resume `{file_name}`. The system currently does not support direct file parsing. Please directly tell me your **major, target city, and expected position**, and I will match them for you precisely."


# --- 5. Helper Function: Load sensitive info from .ini ---
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