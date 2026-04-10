FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Lua + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    lua5.4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (no CUDA needed — LLM runs in Ollama container)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Source code
COPY src/ src/
COPY ui/ ui/
COPY data/ data/
COPY main.py .

# Build FAISS index at build time
RUN python -c "from src.rag_engine import RAGEngine; rag = RAGEngine(); rag.build_index(); print(f'Index built: {len(rag.entries)} entries')"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["python", "main.py"]
CMD ["server", "--port", "8080", "--ollama-host", "http://ollama:11434"]
