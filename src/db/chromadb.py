"""ChromaDB handler with SentenceTransformer embeddings."""

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbedding(EmbeddingFunction):
    """Custom embedding function for ChromaDB using SentenceTransformer."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = self._model.encode(input, show_progress_bar=False)
        return embeddings.tolist()


class ChromaDBHandler:
    """Handles ChromaDB operations with custom embeddings."""

    def __init__(self, path: str = "./data", model_name: str = "all-MiniLM-L6-v2"):
        self.client = chromadb.PersistentClient(path=path)
        self._collections: dict[str, chromadb.Collection] = {}
        self._embedding_fn = SentenceTransformerEmbedding(model_name)

    def get_collection(self, name: str = "technical_docs") -> chromadb.Collection:
        """Get or create collection with custom embedding function."""
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self._embedding_fn,
            )
        return self._collections[name]

    def add_document(
        self,
        id: str,
        text: str,
        metadata: dict | None = None,
        collection_name: str = "technical_docs",
    ) -> None:
        """Add a single document."""
        collection = self.get_collection(collection_name)
        collection.add(
            documents=[text],
            metadatas=[metadata] if metadata else None,
            ids=[id],
        )

    def add_documents_batch(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
        collection_name: str = "technical_docs",
    ) -> None:
        """Add multiple documents in batches.

        ChromaDB has a batch limit of ~5461 items per add() call.
        If len(ids) > 5000, split into sub-batches.
        """
        collection = self.get_collection(collection_name)
        batch_size = 5000

        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            collection.add(
                ids=ids[i:batch_end],
                documents=texts[i:batch_end],
                metadatas=metadatas[i:batch_end] if metadatas else None,
            )

    def search(
        self,
        query: str,
        limit: int = 10,
        collection_name: str = "technical_docs",
        where: dict | None = None,
    ) -> dict:
        """Search documents with optional filters."""
        collection = self.get_collection(collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where,
        )
        return results

    def delete(self, id: str, collection_name: str = "technical_docs") -> None:
        """Delete a document by ID."""
        collection = self.get_collection(collection_name)
        collection.delete(ids=[id])

    def count(self, collection_name: str = "technical_docs") -> int:
        """Get document count."""
        collection = self.get_collection(collection_name)
        return collection.count()

    def delete_collection(self, name: str = "technical_docs") -> None:
        """Delete a collection."""
        if name in self._collections:
            del self._collections[name]
        self.client.delete_collection(name)

    def reset(self) -> None:
        """Reset entire database."""
        self.client.reset()
