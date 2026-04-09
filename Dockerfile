FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    lua5.4 \
    build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps — torch with CUDA 11.8 supports V100 (CC 7.0)
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu118 && \
    pip3 install --no-cache-dir -r requirements.txt

# Build llama-cpp-python with CUDA from source (ensures correct CUDA arch)
RUN CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=70" \
    pip3 install --no-cache-dir llama-cpp-python

# Copy source code
COPY src/ src/
COPY data/ data/
COPY main.py .

# Build FAISS index at build time (embedding model downloaded here)
RUN python3 -c "from src.rag_engine import RAGEngine; rag = RAGEngine(); rag.build_index(); print(f'Index built: {len(rag.entries)} entries')"

# Model mounted as volume (not baked into image)
VOLUME /app/models

EXPOSE 8080

ENTRYPOINT ["python3", "main.py"]
CMD ["server", "--port", "8080", "--lua-binary", "lua5.4"]
