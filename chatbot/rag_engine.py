# rag_engine.py
import pandas as pd
import os
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import RAGConfig, EXCEL_FILE_PATH

logger = logging.getLogger(__name__)


class SimpleJobRAG:
    def __init__(self, excel_path=None):
        # 优先使用传入路径，否则使用 config 中的默认路径
        self.excel_path = excel_path if excel_path else EXCEL_FILE_PATH
        self.df = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.job_texts = []
        self.job_details = []

        self._load_and_index()

    def _load_and_index(self):
        if not os.path.exists(self.excel_path):
            logger.error(f"Excel file not found: {self.excel_path}")
            return

        try:
            self.df = pd.read_excel(self.excel_path)
            logger.info(f"Loaded {len(self.df)} jobs from Excel.")
        except Exception as e:
            logger.error(f"Failed to load Excel: {e}")
            return

        for _, row in self.df.iterrows():
            # 构建检索文本 (用于计算相似度)
            search_text = f"{row.get('Company Name', '')} {row.get('Position', '')} {row.get('Work City', '')} {row.get('Education', '')} {row.get('Remarks', '')} {row.get('Company Type', '')}"
            self.job_texts.append(search_text)

            # 构建详细上下文 (用于发送给 LLM)
            detail_parts = [
                f"[Position] {row.get('Position', 'N/A')}",
                f"[Company] {row.get('Company Name', 'N/A')} ({row.get('Company Type', 'N/A')})",
                f"[Work City] {row.get('Work City', 'N/A')}",
                f"[Deadline] {row.get('Deadline', 'N/A')}",
                f"[Education] {row.get('Education', 'N/A')}",
            ]

            if RAGConfig.INCLUDE_METADATA_IN_CONTEXT:
                detail_parts.append(f"[Link] {row.get('Link', row.get('Apply', '无'))}")
                detail_parts.append(f"[Remarks] {row.get('Remarks', '')}")

            self.job_details.append("\n".join(detail_parts))

        # 使用 config 中的参数初始化向量器
        try:
            self.vectorizer = TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=RAGConfig.NGRAM_RANGE,
                max_features=RAGConfig.MAX_FEATURES
            )

            if self.job_texts:
                self.tfidf_matrix = self.vectorizer.fit_transform(self.job_texts)
                logger.info("TF-IDF Indexing complete.")
        except Exception as e:
            logger.error(f"TF-IDF initialization failed: {e}")

    def search(self, query: str, top_k=None):
        if top_k is None:
            top_k = RAGConfig.TOP_K

        if self.vectorizer is None or self.tfidf_matrix is None:
            return ["No job data available."]

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        top_indices = similarities.argsort()[-top_k:][::-1]

        results = []
        threshold = RAGConfig.SIMILARITY_THRESHOLD

        for idx in top_indices:
            if similarities[idx] >= threshold:
                results.append(self.job_details[idx])
            else:
                # 如果当前索引的相似度已经低于阈值，后续的肯定也低于，可以提前停止
                if not results:
                    # 如果连第一个都没达到阈值
                    logger.info(
                        f"No matches found above threshold {threshold}. Max similarity: {similarities[idx]:.4f}")
                    return ["No positions highly matching this description were found in the database."]
                break

        return results if results else ["No relevant job information found."]