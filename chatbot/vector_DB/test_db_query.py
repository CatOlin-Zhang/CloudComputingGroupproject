import chromadb
import pickle
import os
from sentence_transformers import SentenceTransformer
import numpy as np

current_script_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(current_script_dir, "job_chroma_db")
MODEL_NAME = 'BAAI/bge-small-zh-v1.5'
# ----------------

print(f" Connecting to the database：{DB_PATH}")

if not os.path.exists(DB_PATH):
    print(f" Error: Database folder not found '{DB_PATH}'")
    exit(1)

try:
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("job_positions")
    print(f" Successfully connected to the collection, current data volume：{collection.count()}")
except Exception as e:
    print(f" Connection failed：{e}")
    exit(1)

cache_path = os.path.join(DB_PATH, "details_cache.pkl")
details_cache = {}
if os.path.exists(cache_path):
    with open(cache_path, 'rb') as f:
        details_cache = pickle.load(f)
    print(f" Detailed cache loaded ({len(details_cache)} 条)")
else:
    print("️ Warning: Detailed cache file not found, search results will display only metadata.")

print(f" Loading model：{MODEL_NAME} ...")
model = SentenceTransformer(MODEL_NAME)

query_text = "Java BeiJing"
print(f"\n Search query：'{query_text}'")

query_embedding = model.encode(
    [query_text],
    normalize_embeddings=True
).tolist()

results = collection.query(
    query_embeddings=query_embedding,
    n_results=3,
    include=["metadatas", "distances"]
)

if not results['ids'] or not results['ids'][0]:
    print("\n No matching results found.")
else:
    print(f"\n--- Found {len(results['ids'][0])} results ---")
    for i, doc_id in enumerate(results['ids'][0]):
        dist = results['distances'][0][i]
        similarity = 1 - dist
        meta = results['metadatas'][0][i]
        detail = details_cache.get(doc_id, " Detailed context is missing")

        print(f"\n[Result {i + 1}] Similarity：{similarity:.4f}")
        print(f"Company：{meta.get('company')}")
        print(f"Position：{meta.get('position')}")
        print(f"City：{meta.get('city')}")
        print("-" * 30)
        print(detail)
        print("=" * 30)