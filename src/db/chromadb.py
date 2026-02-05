import chromadb
from typing import Optional
from sentence_transformers import SentenceTransformer

class ChromaDBHandler:
    def __init__(self, path: str = "./data"):
        self.client = chromadb.PersistentClient(path=path)
        self._collections: dict[str, chromadb.Collection] = {}
        self._embedding_model= SentenceTransformer("all-MiniLM-L6-v2") 

    def get_collection(self, name: str = "my_collection") -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(name)
        return self._collections[name]

    def add_document(
        self,
        id: str,
        text: str,
        metadata: dict | None = None
    ) -> None:
        collection = self.get_collection()
        collection.add(
            documents=[text],
            metadatas=[metadata] if metadata else None,
            ids=[id]
        )

    def search(
        self,
        query: str,
        limit: int = 10
    ) -> dict:
        collection = self.get_collection()
        results = collection.query(
            query_texts=[query],
            n_results=limit
        )
        return results

    def delete(self, id: str) -> None:
        collection = self.get_collection()
        collection.delete(ids=[id])

    def count(self) -> int:
        collection = self.get_collection()
        return collection.count()

    def delete_collection(self, name: str = "my_collection") -> None:
        if name in self._collections:
            del self._collections[name]
        self.client.delete_collection(name)

    def reset(self) -> None:
        self.client.reset()

db = ChromaDB()
