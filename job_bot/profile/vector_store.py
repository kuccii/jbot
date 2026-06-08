from pathlib import Path
import chromadb
from chromadb.config import Settings


class VectorStore:
    def __init__(self, persist_path: str):
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )

    def store_profile(self, profile_id: str, text: str, metadata: dict | None = None):
        col = self.client.get_or_create_collection("profiles")
        col.upsert(ids=[profile_id], documents=[text], metadatas=[metadata or {}])

    def search_similar(self, query: str, n_results: int = 5):
        col = self.client.get_or_create_collection("profiles")
        return col.query(query_texts=[query], n_results=n_results)
