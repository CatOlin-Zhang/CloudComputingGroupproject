import os
import logging
import pickle
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from chatbot.config import EXCEL_FILE_PATH
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EXCEL_FILE_PATH = EXCEL_FILE_PATH  # 你的 Excel 文件路径
DB_PERSIST_DIR = "./job_chroma_db"  # 数据库保存文件夹
MODEL_NAME = 'BAAI/bge-small-zh-v1.5'  # 嵌入模型


# ----------------------------------

def build_vector_database():

    if not os.path.exists(EXCEL_FILE_PATH):
        logger.error(f"Error: Excel file not found '{EXCEL_FILE_PATH}'")
        return

    logger.info(f"Connecting/creating local database：{os.path.abspath(DB_PERSIST_DIR)}")
    client = chromadb.PersistentClient(path=DB_PERSIST_DIR)

    collection = client.get_or_create_collection(
        name="job_positions",
        metadata={"hnsw:space": "cosine"}
    )

    count = collection.count()
    if count > 0:
        logger.warning(f"Detected {count} entries already exist in the database. To maintain consistency, they will be cleared and re-imported.")
        collection.delete(where={})

    logger.info("Reading Excel file...")
    try:
        df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl')
    except Exception as e:
        logger.error(f"Failed to read Excel：{e}")
        return

    logger.info(f"Loading model：{MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    documents = []
    metadatas = []
    ids = []
    details_cache = {}

    logger.info("Processing data and generating vectors...")

    for idx, row in df.iterrows():
        doc_id = f"job_{idx}"


        safe_get = lambda k: str(row.get(k, '') or '')


        search_text = " ".join([
            safe_get('Company Name'),
            safe_get('Position'),
            safe_get('Work City'),
            safe_get('Education'),
            safe_get('Remarks'),
            safe_get('Company Type')
        ]).strip()

        if not search_text:
            continue


        detail_parts = [
            f"[Position] {safe_get('Position') or 'N/A'}",
            f"[Company] {safe_get('Company Name') or 'N/A'} ({safe_get('Company Type') or 'N/A'})",
            f"[Work City] {safe_get('Work City') or 'N/A'}",
            f"[Deadline] {safe_get('Deadline') or 'N/A'}",
            f"[Education] {safe_get('Education') or 'N/A'}",
        ]

        link = safe_get('Link') or safe_get('Apply') or '无'
        detail_parts.append(f"[Link] {link}")
        if safe_get('Remarks'):
            detail_parts.append(f"[Remarks] {safe_get('Remarks')}")

        details_cache[doc_id] = "\n".join(detail_parts)


        meta = {
            "company": safe_get('Company Name'),
            "position": safe_get('Position'),
            "city": safe_get('Work City'),
            "education": safe_get('Education'),
            "source_id": doc_id
        }

        documents.append(search_text)
        metadatas.append(meta)
        ids.append(doc_id)


    if not documents:
        logger.error("No valid data can be imported.")
        return

    embeddings = model.encode(
        documents,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    ).tolist()


    batch_size = 500
    total_count = len(documents)

    for i in range(0, total_count, batch_size):
        end_idx = min(i + batch_size, total_count)
        collection.add(
            ids=ids[i:end_idx],
            embeddings=embeddings[i:end_idx],
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )
        logger.info(f"Imported {end_idx}/{total_count} records...")

    cache_path = os.path.join(DB_PERSIST_DIR, "details_cache.pkl")
    with open(cache_path, 'wb') as f:
        pickle.dump(details_cache, f)

    logger.info("=" * 50)
    logger.info("Database construction completed!")
    logger.info(f"Data location：{os.path.abspath(DB_PERSIST_DIR)}")
    logger.info(f"Detailed Cache：{cache_path}")
    logger.info(f"Total Records：{collection.count()}")
    logger.info("=" * 50)


if __name__ == "__main__":
    build_vector_database()