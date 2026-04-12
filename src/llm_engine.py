"""LLM Engine — Ollama (primary) + llama-cpp-python (fallback for GPU clusters)."""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")


class LLMEngine:
    """Tries Ollama first. Falls back to llama-cpp-python if Ollama unavailable."""

    def __init__(self, model=None, ollama_base=None, n_ctx=4096, model_path=None, n_gpu_layers=-1, **kw):
        self.model = model or DEFAULT_MODEL
        self.base_url = ollama_base or OLLAMA_BASE
        self.n_ctx = n_ctx
        self._backend = None  # "ollama" or "llama_cpp"
        self._llm = None  # llama_cpp.Llama instance

        # Try Ollama first
        if self._check_ollama():
            self._backend = "ollama"
            print(f"[LLM] Using Ollama ({self.base_url}) model={self.model}")
        else:
            # Fallback to llama-cpp-python
            self._init_llama_cpp(model_path, n_gpu_layers)

    def _check_ollama(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                return any(self.model in m for m in models)
        except Exception:
            return False

    def _init_llama_cpp(self, model_path=None, n_gpu_layers=-1):
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError("Neither Ollama nor llama-cpp-python available. Install one.")

        if not model_path:
            models_dir = Path(__file__).resolve().parent.parent / "models"
            for name in ["qwen2.5-coder-7b-instruct-q5_k_m.gguf",
                         "qwen2.5-coder-7b-instruct-q4_k_m.gguf"]:
                p = models_dir / name
                if p.exists():
                    model_path = str(p)
                    break

        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError("No GGUF model found. Download one to models/")

        self._llm = Llama(
            model_path=model_path, n_ctx=self.n_ctx,
            n_gpu_layers=n_gpu_layers, n_threads=8,
            verbose=False, chat_format="chatml",
        )
        self._backend = "llama_cpp"
        print(f"[LLM] Using llama-cpp-python GPU, model={model_path}")

    def generate(self, system_prompt, user_prompt, max_tokens=256, temperature=0.2, top_p=0.9, stop=None):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self._backend == "ollama":
            return self._ollama_chat(messages, max_tokens, temperature, top_p, stop)
        return self._llama_chat(messages, max_tokens, temperature, top_p, stop)

    def generate_with_history(self, messages, max_tokens=256, temperature=0.2):
        if self._backend == "ollama":
            return self._ollama_chat(messages, max_tokens, temperature)
        return self._llama_chat(messages, max_tokens, temperature)

    def _ollama_chat(self, messages, max_tokens=256, temperature=0.2, top_p=0.9, stop=None):
        payload = {
            "model": self.model, "messages": messages, "stream": False,
            "options": {"temperature": temperature, "top_p": top_p,
                        "num_predict": max_tokens, "num_ctx": self.n_ctx,
                        "stop": stop or []},
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
            return result["message"]["content"].strip()

    def _llama_chat(self, messages, max_tokens=256, temperature=0.2, top_p=0.9, stop=None):
        resp = self._llm.create_chat_completion(
            messages=messages, max_tokens=max_tokens,
            temperature=temperature, top_p=top_p, stop=stop or [],
        )
        return resp["choices"][0]["message"]["content"].strip()

    def check_model_available(self):
        return self._backend is not None
