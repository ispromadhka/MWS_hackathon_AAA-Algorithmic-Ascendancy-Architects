"""RAG Engine — FAISS + SentenceTransformers для Dynamic Few-Shot."""

import json
import os
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "faiss_index.bin"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class RAGEngine:
    """Индексирует knowledge_base.json и ищет релевантный контекст."""

    def __init__(
        self,
        kb_path: str | None = None,
        index_path: str | None = None,
        model_name: str = EMBEDDING_MODEL,
    ):
        self.kb_path = Path(kb_path or DEFAULT_KB_PATH)
        self.index_path = Path(index_path or DEFAULT_INDEX_PATH)
        self.model = SentenceTransformer(model_name, device="cpu")
        self.entries: list[dict] = []
        self.index: faiss.IndexFlatIP | None = None

        if self.kb_path.exists():
            self._load_knowledge_base()

        if self.index_path.exists():
            self._load_index()
        elif self.entries:
            self.build_index()

    def _load_knowledge_base(self):
        with open(self.kb_path, "r", encoding="utf-8") as f:
            self.entries = json.load(f)
        # Also load MWS-specific patterns if available
        mws_path = self.kb_path.parent / "mws_patterns.json"
        if mws_path.exists():
            with open(mws_path, "r", encoding="utf-8") as f:
                mws_entries = json.load(f)
                self.entries.extend(mws_entries)

    def _load_index(self):
        self.index = faiss.read_index(str(self.index_path))

    def build_index(self):
        """Создаёт FAISS индекс из записей knowledge_base."""
        if not self.entries:
            raise ValueError("Knowledge base is empty. Load it first.")

        texts = [
            f"{e['task_type']}: {e['description']}" for e in self.entries
        ]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype=np.float32)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # cosine similarity (normalized)
        self.index.add(embeddings)

        # сохраняем индекс
        os.makedirs(self.index_path.parent, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))

    def retrieve_context(self, query: str, k: int = 2) -> str:
        """Ищет k ближайших записей, возвращает форматированную строку."""
        if self.index is None or not self.entries:
            return ""

        query_vec = self.model.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype=np.float32)

        scores, indices = self.index.search(query_vec, min(k, len(self.entries)))

        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0:
                continue
            entry = self.entries[idx]
            results.append(
                f"--- Example {i+1} (relevance: {score:.3f}) ---\n"
                f"Task type: {entry['task_type']}\n"
                f"Description: {entry['description']}\n"
                f"Best practice code:\n```lua\n{entry['best_practice_code']}\n```\n"
                f"Tests:\n```lua\n{entry['prewritten_tests']}\n```"
            )

        return "\n\n".join(results)

    def add_entry(self, entry: dict):
        """Добавляет новую запись в базу знаний и пересобирает индекс."""
        self.entries.append(entry)
        self._save_knowledge_base()
        self.build_index()

    def _save_knowledge_base(self):
        os.makedirs(self.kb_path.parent, exist_ok=True)
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def reload(self):
        """Перезагружает БД и пересобирает индекс."""
        self._load_knowledge_base()
        self.build_index()
