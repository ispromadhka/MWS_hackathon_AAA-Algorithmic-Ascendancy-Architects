# LocalScript — LLM Agent System for Lua Code Generation

Multi-agent system for automated Lua code generation, testing, and validation. Uses a local 7B LLM with Dynamic Few-Shot RAG, sandboxed execution, and self-repair loops.

## Architecture

```
Task → [RAG] → [Planner] → [Coder] → [Linter] → [Tester] → [Executor] → [Critic]
                   ↑            ↑                                            │
                   │            └──────── Fast Loop (max 3) ────────────────┘
                   └──────────────── Slow Loop (max 2) ─────────────────────┘
```

### Agents

| Agent | Role |
|-------|------|
| **RAG** | Retrieves relevant code examples from FAISS knowledge base using semantic search |
| **Planner** | Generates structured JSON architecture plan with function signatures and edge cases |
| **Coder** | Writes Lua code following the plan and RAG patterns, with Lua-specific guardrails |
| **Linter** | Static analysis via luacheck — catches syntax errors before sandbox execution |
| **Tester** | Generates O(1) property-based and example-based tests |
| **Executor** | Runs code+tests in sandboxed Lua with instruction counting and memory limits |
| **Critic** | Analyzes results, decides: SUCCESS / retry Coder (Fast Loop) / retry Planner (Slow Loop) |

### Key Features

- **Dynamic Few-Shot RAG** — FAISS + all-MiniLM-L6-v2 retrieves the most relevant code pattern for each task
- **Escalation Temperature** — 0.2 → 0.4 → 0.5 on retries to escape repeated errors
- **O(1) Sandbox** — instruction counting (500K limit), memory tracking, restricted environment
- **Experience Bank** — Reflexion-based learning from successes and failures across tasks
- **Structured Planning** — JSON architecture plans with automatic fallback to free text
- **30 Lua Patterns** — Pre-built knowledge base covering strings, tables, algorithms, OOP, HTTP, state machines, and more

## Quick Start

### Prerequisites

- Python 3.10+
- NVIDIA GPU with CUDA
- Lua 5.4
- (Optional) luacheck for static analysis

### Setup

```bash
# Clone and enter
git clone <repo-url>
cd LocalScript

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install llama-cpp-python  # add CUDA flags if needed: CMAKE_ARGS="-DGGML_CUDA=on"
pip install -r requirements.txt

# Download the model (4.7 GB)
pip install huggingface-hub
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Qwen/Qwen2.5-Coder-7B-Instruct-GGUF',
    filename='qwen2.5-coder-7b-instruct-q4_k_m.gguf',
    local_dir='models/',
)
"

# Build FAISS index
python3 main.py build-rag
```

### Usage

```bash
# Solve a single task
python3 main.py solve --task "Write a Lua function that reverses a string"

# Interactive mode
python3 main.py solve --interactive

# Start HTTP API server
python3 main.py server --port 8080

# Batch evaluation
python3 main.py evaluate --eval-file data/eval_tasks.json
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/solve` | Solve a task. Body: `{"task": "..."}` |
| POST | `/rag/reload` | Reload knowledge base and rebuild index |
| GET | `/health` | Health check with Lua/RAG status |

## Docker

```bash
# Build image
docker compose build

# Run server (single GPU)
docker compose up -d local-script

# Scale to multiple workers
docker compose --profile scale up -d --scale worker=3

# Interactive CLI
docker compose --profile cli run solve

# Batch evaluation
docker compose --profile eval run evaluate
```

## Project Structure

```
├── data/
│   ├── knowledge_base.json    # 30 Lua patterns with tests
│   ├── eval_tasks.json        # Evaluation dataset (10 tasks)
│   ├── faiss_index.bin        # Generated FAISS index
│   └── experience_bank.json   # Auto-generated insights from runs
├── models/
│   └── qwen2.5-coder-7b-instruct-q4_k_m.gguf  # LLM (download separately)
├── src/
│   ├── llm_engine.py          # llama-cpp-python wrapper
│   ├── rag_engine.py          # FAISS + SentenceTransformers
│   ├── sandbox.py             # Lua execution sandbox with limits
│   ├── graph.py               # LangGraph agent orchestration
│   ├── experience_bank.py     # Reflexion-based experience storage
│   └── agents/
│       ├── planner.py         # Architecture planning agent
│       ├── coder.py           # Code generation agent
│       ├── tester.py          # Test generation agent
│       └── critic.py          # Result analysis and routing agent
├── main.py                    # CLI/Server/Eval entry point
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Knowledge Base

The system ships with 30 pre-built Lua patterns covering:

- String manipulation (split, trim, reverse, interpolate, Caesar cipher, palindrome)
- Table operations (map/filter/reduce, deep copy, sort, flatten, unique)
- Data structures (stack, queue, linked list, LRU cache)
- Algorithms (binary search, Levenshtein distance, matrix multiply, GCD/LCM, Fibonacci)
- Patterns (JSON encoding, HTTP parsing, config parsing, rate limiting, state machines)
- OOP (metatables, inheritance), coroutines, error handling, file operations, data validation

### Adding Custom Patterns

Edit `data/knowledge_base.json`:

```json
{
  "task_type": "your_domain",
  "description": "What this pattern does",
  "best_practice_code": "function example() ... end",
  "prewritten_tests": "test_assert_eq(example(), expected, 'test name')"
}
```

Then rebuild the index:

```bash
python3 main.py build-rag
```

## Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--model-path` | `models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` | Path to GGUF model |
| `--ctx-size` | 8192 | Context window size |
| `--gpu-layers` | -1 (all) | Number of GPU layers |
| `--timeout` | 3 | Lua sandbox timeout (seconds) |
| `--lua-binary` | auto-detect | Path to Lua interpreter |
| `--port` | 8080 | Server port |

## Sandbox Security

The Lua sandbox enforces:

- **Instruction limit**: 500,000 instructions via `debug.sethook` (prevents infinite loops)
- **Memory tracking**: Reports memory usage via `collectgarbage`
- **Timeout**: Configurable process-level timeout (default 3s)
- **Restricted environment**: `os.execute`, `io.popen`, `loadfile`, `dofile` are disabled
- **Static analysis**: Optional luacheck pre-execution catches errors before running

## Benchmarks

| Task | Result | TTS | Memory |
|------|--------|-----|--------|
| Binary search | Pass@1 | 6.4s | 1.2 KB |
| Levenshtein distance | Pass@1 | 7.0s | 1.2 KB |
| Caesar cipher | Pass@2 | 10.6s | 1.3 KB |
| Matrix multiplication | Pass@3 | 16.8s | 3.9 KB |

All tests execute in O(1) time and memory.

## License

See [LICENSE](LICENSE).
