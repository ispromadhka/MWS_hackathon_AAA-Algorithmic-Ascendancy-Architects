"""Experience Bank — хранит инсайты из успехов и провалов для Reflexion."""

import json
import os
from pathlib import Path

import numpy as np


DEFAULT_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "experience_bank.json"


class ExperienceBank:
    """Накапливает инсайты из решённых задач, ищет релевантные."""

    def __init__(self, bank_path: str | None = None, rag_engine=None):
        self.bank_path = Path(bank_path or DEFAULT_BANK_PATH)
        self.rag_engine = rag_engine  # Reuse the RAG's embedding model
        self.entries: list[dict] = []

        if self.bank_path.exists():
            with open(self.bank_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)

    def add_insight(self, task_type: str, insight: str, source: str = "failure"):
        """Добавляет инсайт из опыта решения задачи."""
        entry = {
            "task_type": task_type,
            "insight": insight,
            "source": source,  # "success" | "failure"
        }
        # Дедупликация: не добавлять если уже есть похожий
        for existing in self.entries:
            if existing["insight"] == insight:
                return
        self.entries.append(entry)
        self._save()

    def retrieve_insights(self, query: str, k: int = 2) -> str:
        """Ищет релевантные инсайты через embedding similarity."""
        if not self.entries or not self.rag_engine:
            return ""

        try:
            model = self.rag_engine.model
            query_vec = model.encode([query], normalize_embeddings=True)
            texts = [f"{e['task_type']}: {e['insight']}" for e in self.entries]
            entry_vecs = model.encode(texts, normalize_embeddings=True)

            # Cosine similarity
            scores = np.dot(entry_vecs, query_vec.T).flatten()
            top_indices = np.argsort(scores)[::-1][:k]

            results = []
            for idx in top_indices:
                if scores[idx] < 0.3:  # Skip low-relevance
                    continue
                e = self.entries[idx]
                tag = "TIP" if e["source"] == "success" else "WARNING"
                results.append(f"[{tag}] {e['insight']}")

            return "\n".join(results) if results else ""
        except Exception:
            return ""

    def _save(self):
        os.makedirs(self.bank_path.parent, exist_ok=True)
        with open(self.bank_path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)
