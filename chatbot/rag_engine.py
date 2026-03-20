import pandas as pd
import os
import logging
import torch
from sentence_transformers import SentenceTransformer, util
from config import RAGConfig, EXCEL_FILE_PATH

logger = logging.getLogger(__name__)


class SimpleJobRAG:
    def __init__(self, excel_path=None):
        self.excel_path = excel_path if excel_path else EXCEL_FILE_PATH
        self.df = None
        self.model = None
        self.job_embeddings = None
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

        # 1. Build retrieval text and detailed context
        for _, row in self.df.iterrows():
            search_text = f"{row.get('Company Name', '')} {row.get('Position', '')} {row.get('Work City', '')} {row.get('Education', '')} {row.get('Remarks', '')} {row.get('Company Type', '')}"
            self.job_texts.append(search_text)

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

        # 2. Initialize the model
        try:
            model_name = getattr(RAGConfig, 'EMBEDDING_MODEL_NAME', 'BAAI/bge-small-zh-v1.5')
            logger.info(f"Loading Neural Search model: {model_name} ...")
            self.model = SentenceTransformer(model_name)

            if self.job_texts:
                logger.info("Encoding job descriptions into vectors...")
                self.job_embeddings = self.model.encode(
                    self.job_texts,
                    batch_size=32,
                    show_progress_bar=True,
                    convert_to_tensor=True
                )
                logger.info(f"Neural Indexing complete. Vector shape: {self.job_embeddings.shape}")
        except Exception as e:
            logger.error(f"Neural Search initialization failed: {e}")
            raise e

    def search(self, query: str, top_k=None):
        if top_k is None:
            top_k = RAGConfig.TOP_K

        if self.model is None or self.job_embeddings is None:
            return ["No job data available."]

        try:
            # 1. Code Lookup
            query_embedding = self.model.encode(query, convert_to_tensor=True)

            # 2. Calculate cosine similarity
            # cos_scores  [1, num_jobs]
            cos_scores = util.cos_sim(query_embedding, self.job_embeddings)[0]


            k = min(top_k, len(cos_scores))

            # # torch.topk returns (values, indices), sorted in descending order
            top_results = torch.topk(cos_scores, k=k)

            scores = top_results[0].cpu().numpy()
            indices = top_results[1].cpu().numpy()

            results = []
            threshold = RAGConfig.SIMILARITY_THRESHOLD

            # Used for debug logs
            max_score = scores[0] if len(scores) > 0 else 0
            logger.info(f"Query: '{query}' | Max Similarity Score: {max_score:.4f}")

            for i, idx in enumerate(indices):
                score = scores[i]

                # Strategy A: Strict Match (Above Threshold)
                if score >= threshold:
                    results.append(self.job_details[idx])
                else:
                    # If the current score is lower than the threshold, since it is in descending order, the following ones will definitely be lower
                    # If the result is empty, try to return the best one
                    if not results and score > 0.4:
                        logger.warning(
                            f"No strict matches (>={threshold}), but found a potential match with score {score:.4f}. Returning best effort.")
                        results.append(self.job_details[idx])
                        break
                    elif not results:
                        logger.info(f"No matches found above threshold {threshold} or fallback limit (0.4).")
                        return [
                            "No positions highly matching this description were found in the database. Suggest trying specific keywords like 'Java', 'Beijing', or company names."]
                    break

            if not results:
                return ["No relevant job information found."]

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return ["Error occurred during neural search."]